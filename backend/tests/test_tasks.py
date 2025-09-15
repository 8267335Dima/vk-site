# backend/tests/test_tasks.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from arq.worker import Worker

from app.db.models import User, TaskHistory
from app.core.constants import PlanName
from app.worker import WorkerSettings
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.core.config import settings

# Помечаем все тесты в файле как асинхронные
pytestmark = pytest.mark.asyncio

# --- Глобальные переменные для тестовой среды ---
TEST_FRIEND_VK_ID = int(settings.VK_TEST_FRIEND_ID)
GROUP_TO_JOIN_LEAVE = "memes" # Ключевое слово для поиска группы
GROUP_TO_JOIN_SECOND = "science_technology" # Для теста на вступление

# --- ОСНОВНАЯ ФИКСТУРА ПОДГОТОВКИ ---
@pytest.fixture(scope="module", autouse=True)
async def prepare_vk_environment(db_session: AsyncSession, async_client: AsyncClient):
    """
    Эта мощная фикстура запускается один раз перед всеми тестами в этом файле.
    Она подготавливает тестовый аккаунт VK для реальных действий:
    1. Авторизуется и получает токен.
    2. Создает полноценный VK API клиент.
    3. Переводит пользователя на PRO тариф.
    4. Очищает историю его задач.
    5. ПРИНУДИТЕЛЬНО ДОБАВЛЯЕТ тестового друга для тестов рассылки/удаления.
    6. ПРИНУДИТЕЛЬНО ВСТУПАЕТ в тестовую группу для теста выхода.
    7. После всех тестов - удаляет друга и выходит из группы, очищая за собой.
    """
    print("\n[MODULE SETUP] Начало подготовки тестовой среды VK...")
    
    # 1. Авторизация и создание VK API клиента
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": settings.VK_HEALTH_CHECK_TOKEN})
    assert response.status_code == 200
    user_id = response.json()['manager_id']
    
    user = await db_session.get(User, user_id)
    assert user is not None
    vk_token = decrypt_data(user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)

    # 2. Настройка пользователя в нашей БД
    user.plan = PlanName.PRO
    await db_session.execute(delete(TaskHistory).where(TaskHistory.user_id == user.id))
    await db_session.commit()
    print("[MODULE SETUP] Пользователь переведен на PRO, история задач очищена.")

    # 3. Подготовка друга
    try:
        print(f"[MODULE SETUP] Попытка удалить друга {TEST_FRIEND_VK_ID} для чистоты теста...")
        await vk_api.delete_friend(TEST_FRIEND_VK_ID)
        await asyncio.sleep(2) # Пауза после удаления
    except Exception:
        print("[MODULE SETUP] Друг не был в друзьях, это нормально.")
    
    print(f"[MODULE SETUP] Отправка заявки в друзья пользователю {TEST_FRIEND_VK_ID}...")
    await vk_api.add_friend(TEST_FRIEND_VK_ID)
    print(f"[MODULE SETUP] ВАЖНО: Для прохождения тестов убедитесь, что аккаунт {TEST_FRIEND_VK_ID} ПРИНЯЛ эту заявку!")
    
    # 4. Подготовка группы
    try:
        print(f"[MODULE SETUP] Поиск группы по ключевому слову '{GROUP_TO_JOIN_LEAVE}'...")
        groups = await vk_api.search_groups(query=GROUP_TO_JOIN_LEAVE, count=1)
        group_id = groups['items'][0]['id']
        
        print(f"[MODULE SETUP] Попытка покинуть группу {group_id} для чистоты теста...")
        await vk_api.leave_group(group_id)
        await asyncio.sleep(2)
    except Exception:
        print("[MODULE SETUP] Не состояли в группе, это нормально.")
        
    print(f"[MODULE SETUP] Вступление в группу {group_id}...")
    await vk_api.join_group(group_id)

    # Передаем управление тестам
    yield

    # 5. Очистка после всех тестов
    print("\n[MODULE TEARDOWN] Очистка тестовой среды VK...")
    try:
        print(f"[MODULE TEARDOWN] Удаление друга {TEST_FRIEND_VK_ID}...")
        await vk_api.delete_friend(TEST_FRIEND_VK_ID)
    except Exception as e:
        print(f"[MODULE TEARDOWN] Не удалось удалить друга: {e}")
        
    try:
        groups = await vk_api.search_groups(query=GROUP_TO_JOIN_LEAVE, count=1)
        group_id = groups['items'][0]['id']
        print(f"[MODULE TEARDOWN] Выход из группы {group_id}...")
        await vk_api.leave_group(group_id)
    except Exception as e:
        print(f"[MODULE TEARDOWN] Не удалось покинуть группу: {e}")
    print("[MODULE TEARDOWN] Очистка завершена.")


async def _run_and_verify_task(
    async_client: AsyncClient,
    db_session: AsyncSession,
    headers: dict,
    task_key: str,
    payload: dict
):
    """Хелпер: запускает задачу и проверяет ее успешное выполнение."""
    print(f"\n--- Тестирование задачи: {task_key} ---")
    
    response = await async_client.post(f"/api/v1/tasks/run/{task_key}", headers=headers, json=payload)
    assert response.status_code == 200, f"API вернул ошибку: {response.text}"
    job_id = response.json()['task_id']
    print(f"[ACTION] Задача {job_id} успешно поставлена в очередь.")

    print("[TEST] Запускаем воркер ARQ в режиме 'burst'...")
    worker = Worker(
        functions=WorkerSettings.functions, redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup, on_shutdown=WorkerSettings.on_shutdown,
        burst=True, poll_delay=0
    )
    await worker.main()
    print("[TEST] Воркер ARQ отработал.")

    db_session.expire_all()
    completed_task = await db_session.scalar(
        select(TaskHistory).where(TaskHistory.celery_task_id == job_id)
    )
    
    assert completed_task is not None, "Задача не найдена в истории после выполнения воркера"
    print(f"[VERIFY] Финальный статус: {completed_task.status}. Результат: {completed_task.result}")
    print("------ ЛОГИ ВОРКЕРА (stdout) ------")
    # Pytest выведет здесь логи из stdout, где будут ссылки
    print("-----------------------------------")
    assert completed_task.status == "SUCCESS", f"Ожидался SUCCESS, но задача провалилась."
    
    print(f"[SUCCESS] ✓ Тест для задачи '{task_key}' пройден.")

# --- РЕАЛЬНЫЕ ТЕСТЫ ДЛЯ КАЖДОЙ ЗАДАЧИ ---

async def test_task_like_feed(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест: ставит 4 реальных лайка в ленте новостей."""
    _, headers = authorized_user_and_headers
    await _run_and_verify_task(async_client, db_session, headers, "like_feed", {"count": 4})

async def test_task_view_stories(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест: реально просматривает все доступные истории."""
    _, headers = authorized_user_and_headers
    await _run_and_verify_task(async_client, db_session, headers, "view_stories", {})

async def test_task_accept_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Тест: пытается принять входящие заявки.
    ВАЖНО: Для 100% проверки этого теста, тестовый друг (VK_TEST_FRIEND_ID)
    должен ОТПРАВИТЬ заявку в друзья основному тестовому аккаунту ПЕРЕД запуском.
    Если заявок нет, тест все равно пройдет, т.к. задача отработает корректно.
    """
    _, headers = authorized_user_and_headers
    await _run_and_verify_task(async_client, db_session, headers, "accept_friends", {"filters": {}})

async def test_task_join_groups(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест: вступает в 2 реальные группы по ключевому слову."""
    _, headers = authorized_user_and_headers
    payload = {"count": 2, "filters": {"status_keyword": GROUP_TO_JOIN_SECOND}}
    await _run_and_verify_task(async_client, db_session, headers, "join_groups", payload)

async def test_task_leave_groups(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест: выходит из группы, в которую вступил в фикстуре подготовки."""
    _, headers = authorized_user_and_headers
    payload = {"count": 1, "filters": {"status_keyword": GROUP_TO_JOIN_LEAVE}}
    await _run_and_verify_task(async_client, db_session, headers, "leave_groups", payload)
    
async def test_task_remove_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест: удаляет друга, который был добавлен в фикстуре подготовки."""
    _, headers = authorized_user_and_headers
    # Удаляем по любому критерию, которому друг соответствует. 
    # Так как мы его только что добавили, он точно был недавно в сети.
    payload = {"count": 1, "filters": {"last_seen_hours": 1}}
    await _run_and_verify_task(async_client, db_session, headers, "remove_friends", payload)
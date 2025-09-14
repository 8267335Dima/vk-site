import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.models import User, FriendRequestLog, TaskHistory, Payment
from app.core.constants import PlanName
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
import datetime

# Помечаем все тесты в файле как асинхронные
pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="module")
async def vk_api_client(authorized_user_and_headers: tuple) -> VKAPI:
    """
    Создает ОДИН раз на весь тестовый модуль реальный клиент VK API,
    чтобы не пересоздавать его для каждого теста.
    """
    user, _ = authorized_user_and_headers
    token = decrypt_data(user.encrypted_vk_token)
    assert token, "Не удалось получить токен для VK API клиента"
    print("\n[SETUP] Создан реальный клиент VK API для тестов.")
    return VKAPI(access_token=token)


async def test_billing_webhook_works_on_real_db(
    async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple
):
    """
    Тест для биллинга. Он не трогает VK API, но работает с реальной БД,
    поэтому логично держать его здесь.
    """
    print("\n--- Тест: Цикл обработки платежа на реальной БД ---")
    user, headers = authorized_user_and_headers
    
    user.plan = "Expired"
    user.plan_expires_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(user)

    payment_system_id = f"test_payment_{datetime.datetime.utcnow().timestamp()}"
    new_payment = Payment(
        payment_system_id=payment_system_id, user_id=user.id, amount=699.0,
        status="pending", plan_name="Plus", months=1
    )
    db_session.add(new_payment)
    await db_session.flush()
    payment_id = new_payment.id
    await db_session.commit()
    print(f"[INFO] В БД создан тестовый платеж ID={payment_id} со статусом 'pending'")

    webhook_payload = {
        "event": "payment.succeeded",
        "object": { "id": payment_system_id, "status": "succeeded", "amount": {"value": "699.00", "currency": "RUB"}, "paid": True }
    }
    print("[ACTION] Отправляем фейковый вебхук на наш API...")
    response = await async_client.post("/api/v1/billing/webhook", json=webhook_payload)
    assert response.status_code == 200

    await db_session.refresh(user)
    print(f"[VERIFY] План пользователя обновлен на: {user.plan}")
    assert user.plan == "Plus"
    
    updated_payment = await db_session.get(Payment, payment_id)
    assert updated_payment is not None
    print(f"[VERIFY] Статус платежа в БД обновлен на: {updated_payment.status}")
    assert updated_payment.status == "succeeded"
    print("[SUCCESS] ✓ Тест биллинга пройден.")


async def test_real_add_friend_cycle(
    async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI
):
    """
    Полный реальный цикл: НАХОДИТ -> ДОБАВЛЯЕТ -> ПРОВЕРЯЕТ -> ОТМЕНЯЕТ
    """
    user, headers = authorized_user_and_headers
    print("\n--- Тест: Реальное добавление друга из рекомендаций ---")
    user.plan = PlanName.PRO
    user.plan_expires_at = None
    await db_session.commit()
    
    print("[API] Получаем реальный список рекомендуемых друзей из VK...")
    recommendations = await vk_api_client.get_recommended_friends(count=10)
    assert recommendations and recommendations.get('items'), "VK API не вернул рекомендуемых друзей."
    
    target_user = recommendations['items'][0]
    target_vk_id = target_user['id']
    target_name = f"{target_user['first_name']} {target_user['last_name']}"
    target_url = f"https://vk.com/id{target_vk_id}"
    print(f"[INFO] Выбрана реальная цель для добавления: {target_name} ({target_url})")
    
    # Очистка "до"
    await vk_api_client.delete_friend(target_vk_id)
    await db_session.execute(delete(FriendRequestLog).where(FriendRequestLog.target_vk_id == target_vk_id, FriendRequestLog.user_id == user.id))
    await db_session.commit()
    print(f"[SETUP] Предыдущие заявки для {target_name} отменены.")

    # Запуск задачи
    add_payload = { "count": 1 }
    print("[ACTION] Запускаем задачу 'Добавление друзей' через наше API...")
    response = await async_client.post("/api/v1/tasks/run/add_recommended", headers=headers, json=add_payload)
    assert response.status_code == 200, f"Задача на добавление не запустилась: {response.text}"
    task_id = response.json()['task_id']

    # Ожидание и проверка
    print(f"[WAIT] Ожидаем 15 секунд для выполнения реального запроса Celery...")
    await asyncio.sleep(15)
    
    task_history = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == task_id))
    assert task_history is not None, "Запись в истории задач не найдена!"
    print(f"[VERIFY] Статус задачи в истории: {task_history.status}. Результат: {task_history.result}")
    assert task_history.status == "SUCCESS", "Задача не выполнилась успешно."

    friend_log = await db_session.scalar(select(FriendRequestLog).where(FriendRequestLog.user_id == user.id, FriendRequestLog.target_vk_id == target_vk_id))
    assert friend_log is not None, f"В БД не найдена запись об отправке заявки пользователю {target_name}!"
    print(f"[SUCCESS] ✓ В БД создана запись о заявке для {target_name}.")

    # Очистка "после"
    print(f"[CLEANUP] Отменяем отправленную заявку в друзья для {target_name}...")
    await vk_api_client.delete_friend(target_vk_id)
    print("[CLEANUP] Очистка завершена.")


async def test_real_like_feed(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    РЕАЛЬНЫЙ ТЕСТ: Запускает задачу проставления лайков в ленте и проверяет ее успешное выполнение.
    """
    user, headers = authorized_user_and_headers
    print("\n--- Тест: Реальный запуск проставления лайков в ленте ---")
    user.plan = PlanName.PRO
    user.plan_expires_at = None
    await db_session.commit()

    like_payload = {"count": 5, "filters": {"only_with_photo": True}}
    print("[ACTION] Запускаем задачу 'Лайки в ленте новостей'...")
    response = await async_client.post("/api/v1/tasks/run/like_feed", headers=headers, json=like_payload)
    assert response.status_code == 200, f"Задача 'Лайки в ленте' не запустилась: {response.text}"
    task_id = response.json()['task_id']

    print(f"[WAIT] Ожидаем 15 секунд для выполнения задачи...")
    await asyncio.sleep(15)
    
    task_history = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == task_id))
    assert task_history is not None, "Запись в истории задач не найдена!"
    print(f"[VERIFY] Статус задачи в истории: {task_history.status}. Результат: {task_history.result}")
    assert task_history.status == "SUCCESS", "Задача не выполнилась успешно."
    print(f"[SUCCESS] ✓ Задача проставления лайков выполнилась без ошибок.")


async def test_real_join_and_leave_group(
    async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI
):
    """
    РЕАЛЬНЫЙ ТЕСТ: Находит группу, вступает в нее, проверяет, а затем выходит.
    """
    user, headers = authorized_user_and_headers
    print("\n--- Тест: Реальный цикл вступления и выхода из группы ---")
    user.plan = PlanName.PRO
    user.plan_expires_at = None
    await db_session.commit()

    # Поиск цели
    SEARCH_KEYWORD = "Наука"
    print(f"[API] Ищем реальную группу по ключевому слову '{SEARCH_KEYWORD}'...")
    groups = await vk_api_client.search_groups(query=SEARCH_KEYWORD, count=10)
    assert groups and groups.get('items'), f"VK API не нашел групп по запросу '{SEARCH_KEYWORD}'."
    target_group = groups['items'][0]
    target_group_id = target_group['id']
    target_group_name = target_group['name']
    print(f"[INFO] Выбрана цель для вступления: '{target_group_name}' (vk.com/club{target_group_id})")

    # Очистка "до"
    await vk_api_client.leave_group(target_group_id)
    print(f"[SETUP] Вышли из группы '{target_group_name}', если состояли в ней.")
    
    # Запуск задачи на вступление
    join_payload = {"count": 1, "filters": {"status_keyword": SEARCH_KEYWORD}}
    print("[ACTION] Запускаем задачу 'Вступление в группы'...")
    response_join = await async_client.post("/api/v1/tasks/run/join_groups", headers=headers, json=join_payload)
    assert response_join.status_code == 200, f"Задача на вступление не запустилась: {response_join.text}"
    task_id_join = response_join.json()['task_id']
    
    print("[WAIT] Ожидаем 10 секунд для вступления...")
    await asyncio.sleep(10)
    
    task_history_join = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == task_id_join))
    assert task_history_join.status == "SUCCESS", "Задача на вступление не выполнилась успешно."
    print("[VERIFY] Задача на вступление в группу выполнена.")

    # Проверка результата через API
    user_groups_after_join = await vk_api_client.get_groups(user.vk_id, extended=0)
    assert target_group_id in user_groups_after_join['items'], f"Не удалось подтвердить вступление в группу '{target_group_name}'!"
    print(f"[SUCCESS] ✓ Подтверждено: пользователь теперь состоит в группе '{target_group_name}'.")

    # Запуск задачи на выход
    leave_payload = {"count": 1, "filters": {"status_keyword": SEARCH_KEYWORD}}
    print("[ACTION] Запускаем задачу 'Отписка от сообществ' для очистки...")
    response_leave = await async_client.post("/api/v1/tasks/run/leave_groups", headers=headers, json=leave_payload)
    assert response_leave.status_code == 200, f"Задача на выход не запустилась: {response_leave.text}"
    
    print("[WAIT] Ожидаем 10 секунд для выхода...")
    await asyncio.sleep(10)

    user_groups_after_leave = await vk_api_client.get_groups(user.vk_id, extended=0)
    assert target_group_id not in user_groups_after_leave['items'], f"Не удалось подтвердить выход из группы '{target_group_name}'!"
    print(f"[CLEANUP] ✓ Подтверждено: пользователь успешно покинул группу.")
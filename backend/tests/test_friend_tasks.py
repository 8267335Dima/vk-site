# backend/tests/test_friend_tasks.py (ПОЛНАЯ ОБНОВЛЕННАЯ ВЕРСИЯ)

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task

pytestmark = pytest.mark.asyncio

async def test_add_friends_from_recommended(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    """Находит 2 пользователей в рекомендациях и отправляет им заявки, разрешая закрытые профили."""
    print("\n--- Тестирование задачи: 'Добавить друзей из рекомендаций' (с закрытыми профилями) ---")
    user, headers = authorized_user_and_headers
    
    recommendations = await vk_api_client.get_recommended_friends(count=10)
    assert recommendations and len(recommendations.get('items', [])) >= 2, "Для теста нужно как минимум 2 рекомендации от VK."
    
    payload = {"count": 2, "filters": {"allow_closed_profiles": True}} # ЯВНО РАЗРЕШАЕМ
    await run_and_verify_task(async_client, db_session, headers, "add_recommended", payload, user.id)

async def test_scenario_add_and_like(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    """
    Тест-сценарий:
    1. Находит 1 человека в рекомендациях.
    2. Отправляет ему заявку в друзья, но ищет ТОЛЬКО ОТКРЫТЫЕ ПРОФИЛИ.
    3. Включает опцию лайка аватара и стены после отправки.
    4. Проверяет, что задача выполнилась и лайки были поставлены.
    """
    print("\n--- Тестирование сценария: 'Добавить в друзья и пролайкать' (только открытые) ---")
    user, headers = authorized_user_and_headers

    # Ищем среди 20 рекомендаций, чтобы повысить шанс найти открытый профиль
    recommendations = await vk_api_client.get_recommended_friends(count=20)
    assert recommendations and recommendations.get('items'), "Для теста нужны рекомендации от VK."
    
    payload = {
        "count": 1,
        "filters": {"allow_closed_profiles": False}, # КЛЮЧЕВОЕ ОТЛИЧИЕ: ищем только открытые
        "like_config": {
            "enabled": True,
            "targets": ["avatar", "wall"] # Лайкаем и аватар, и стену
        }
    }
    
    task_result = await run_and_verify_task(async_client, db_session, headers, "add_recommended", payload, user.id)

    # Проверяем логи задачи, чтобы убедиться, что лайки были поставлены
    task_logs_str = task_result.result 
    # Может случиться, что у пользователя нет постов на стене или фото.
    # Поэтому проверяем, что хотя бы один лайк был поставлен.
    assert "Поставлен лайк" in task_logs_str, "В логах нет упоминания о лайках"
    print("✓ Задача 'Добавить и пролайкать' успешно выполнена, в логах есть подтверждение лайков.")


async def test_remove_friends_by_filter(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    """Удаляет 3 друзей по фильтру "забаненные" (собачки)."""
    print("\n--- Тестирование задачи: 'Удалить друзей по критериям' ---")
    user, headers = authorized_user_and_headers
    
    initial_friends_data = await vk_api_client.get_user_friends(user.vk_id, fields="deactivated")
    initial_count = initial_friends_data['count']
    banned_count = len([f for f in initial_friends_data['items'] if f.get('deactivated')])
    
    print(f"[PREP] Текущее количество друзей: {initial_count}. Из них 'собачек': {banned_count}")
    
    remove_count = 3
    if banned_count < remove_count:
        pytest.skip(f"Тест на удаление пропущен: для него нужно как минимум {remove_count} забаненных друга, а найдено {banned_count}.")
        
    payload = {"count": remove_count, "filters": {"remove_banned": True}}
    await run_and_verify_task(async_client, db_session, headers, "remove_friends", payload, user.id)
    
    print("[VERIFY] Пауза 5 секунд для синхронизации VK...")
    await asyncio.sleep(5)
    
    final_friends_data = await vk_api_client.get_user_friends(user.vk_id, fields="")
    final_count = final_friends_data['count']
    print(f"[VERIFY] Количество друзей после удаления 'собачек': {final_count}")
    
    assert final_count <= initial_count - remove_count
    print("✓ Проверка 'было/стало' для удаления друзей пройдена.")

async def test_task_accept_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест пытается принять входящие заявки."""
    print("\n--- Тестирование задачи: 'Принять заявки в друзья' ---")
    print("[INFO] Для полной проверки этого теста отправьте заявку на ваш тестовый аккаунт с другого профиля.")
    user, headers = authorized_user_and_headers
    # При приеме заявок мы всегда можем получить базовую инфу, поэтому allow_closed_profiles не так важен
    await run_and_verify_task(async_client, db_session, headers, "accept_friends", {"filters": {}}, user.id)

async def test_task_birthday_congratulation(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест запускает задачу поздравления. Успешен, даже если именинников нет."""
    print("\n--- Тестирование задачи: 'Поздравление с Днем Рождения' ---")
    user, headers = authorized_user_and_headers
    payload = {"message_template_default": "С Днем Рождения, {name}! (Автотест)"}
    await run_and_verify_task(async_client, db_session, headers, "birthday_congratulation", payload, user.id)


async def test_add_friends_with_impossible_filters(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Проверяет, что задача корректно завершается со статусом SUCCESS,
    даже если по очень строгим фильтрам не найдено ни одного кандидата.
    """
    print("\n--- Тестирование задачи: 'Добавить друзей' (с невыполнимыми фильтрами) ---")
    user, headers = authorized_user_and_headers
    
    payload = {
        "count": 5, 
        "filters": {
            "allow_closed_profiles": True,
            "city": "ГородКоторогоНетВПрироде12345", # Заведомо невыполнимый фильтр
            "is_online": True
        }
    }
    task_result = await run_and_verify_task(async_client, db_session, headers, "add_recommended", payload, user.id)
    
    assert "Рекомендации не найдены" in task_result.result or "После фильтрации осталось: 0" in task_result.result
    print("✓ Задача корректно отработала ситуацию, когда кандидаты не найдены.")

@pytest.mark.skip(reason="Опасно! Отправляет реальное личное сообщение. Включать для ручной проверки.")
async def test_add_friend_with_welcome_message(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Тестирует одну из ключевых функций: отправку приветственного сообщения при добавлении в друзья.
    """
    print("\n--- Тестирование сценария: 'Добавить в друзья с приветственным сообщением' ---")
    user, headers = authorized_user_and_headers
    
    payload = {
        "count": 1,
        "filters": {"allow_closed_profiles": False}, # Ищем открытые профили, чтобы сообщение точно дошло
        "send_message_on_add": True,
        "message_text": "Привет, {name}! Увидел тебя в рекомендациях, решил добавиться. (Это сообщение отправлено авто-тестом)."
    }
    
    task_result = await run_and_verify_task(async_client, db_session, headers, "add_recommended", payload, user.id)

    assert "Отправлена заявка" in task_result.result and "с сообщением" in task_result.result
    print("✓ В логах задачи есть подтверждение отправки заявки с сообщением.")
# backend/tests/test_friend_tasks.py (Полная финальная версия)
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task

pytestmark = pytest.mark.asyncio

async def test_add_friends_from_recommended(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    """Находит 2 пользователей в рекомендациях и отправляет им заявки."""
    user, headers = authorized_user_and_headers
    
    recommendations = await vk_api_client.get_recommended_friends(count=5)
    assert recommendations and len(recommendations.get('items', [])) >= 2, "Для теста нужно как минимум 2 рекомендации от VK."
    
    payload = {"count": 2, "filters": {"allow_closed_profiles": True}}
    await run_and_verify_task(async_client, db_session, headers, "add_recommended", payload, user.id)

async def test_remove_friends_by_filter(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    """Удаляет 3 друзей по фильтру "забаненные" (собачки)."""
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
    print("\n[INFO] Для полной проверки этого теста отправьте заявку на ваш тестовый аккаунт с другого профиля.")
    user, headers = authorized_user_and_headers
    await run_and_verify_task(async_client, db_session, headers, "accept_friends", {"filters": {}}, user.id)

async def test_task_birthday_congratulation(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Тест запускает задачу поздравления. Успешен, даже если именинников нет."""
    user, headers = authorized_user_and_headers
    payload = {"message_template_default": "С Днем Рождения, {name}! (Автотест)"}
    await run_and_verify_task(async_client, db_session, headers, "birthday_congratulation", payload, user.id)
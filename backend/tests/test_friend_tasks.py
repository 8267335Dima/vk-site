# backend/tests/test_friend_tasks.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task

async def test_add_friends_from_recommended(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    user, headers = authorized_user_and_headers
    recs = await vk_api_client.get_recommended_friends(count=10)
    assert recs and len(recs.get('items', [])) >= 2, "Для теста нужно как минимум 2 рекомендации от VK."
    await run_and_verify_task(async_client, db_session, headers, "add_recommended", {"count": 2, "filters": {"allow_closed_profiles": True}}, user.id)

async def test_scenario_add_and_like(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    payload = { "count": 1, "filters": {"allow_closed_profiles": False}, "like_config": { "enabled": True, "targets": ["avatar", "wall"] } }
    task_result = await run_and_verify_task(async_client, db_session, headers, "add_recommended", payload, user.id)
    assert "Поставлен лайк" in task_result.result

async def test_remove_banned_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    user, headers = authorized_user_and_headers
    initial_data = await vk_api_client.get_user_friends(user.vk_id, fields="deactivated")
    initial_count = initial_data['count']
    banned_count = len([f for f in initial_data['items'] if f.get('deactivated')])
    
    if banned_count < 3: pytest.skip(f"Нужно как минимум 3 забаненных друга, найдено {banned_count}.")
    
    await run_and_verify_task(async_client, db_session, headers, "remove_friends", {"count": 3, "filters": {"remove_banned": True}}, user.id)
    
    await asyncio.sleep(5)
    final_data = await vk_api_client.get_user_friends(user.vk_id)
    assert final_data['count'] <= initial_count - 3

async def test_add_friend_with_welcome_message(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    payload = { "count": 1, "filters": {"allow_closed_profiles": False}, "send_message_on_add": True, "message_text": "Привет, {name}! Увидела тебя в рекомендациях." }
    task_result = await run_and_verify_task(async_client, db_session, headers, "add_recommended", payload, user.id)
    assert "Отправлена заявка" in task_result.result and "с сообщением" in task_result.result
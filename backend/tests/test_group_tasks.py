# backend/tests/test_group_tasks.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task


GROUP_KEYWORD_JOIN = "python"
GROUP_KEYWORD_LEAVE = "memes"

@pytest.fixture(scope="module", autouse=True)
async def prepare_group_environment(vk_api_client: VKAPI):
    print(f"\n[PREP] Подготовка среды для тестов групп...")
    groups = await vk_api_client.search_groups(query=GROUP_KEYWORD_LEAVE, count=3)
    if groups and groups.get('items'):
        for group in groups['items']:
            await vk_api_client.join_group(group['id'])
    
    yield
    
    print(f"\n[CLEANUP] Очистка после тестов групп...")
    joined_groups = await vk_api_client.search_groups(query=GROUP_KEYWORD_JOIN, count=5)
    if joined_groups and joined_groups.get('items'):
        for group in joined_groups['items']:
            await vk_api_client.leave_group(group['id'])

async def test_join_groups(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    user, headers = authorized_user_and_headers
    initial_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    initial_count = initial_data['count'] if initial_data else 0
    
    await run_and_verify_task(async_client, db_session, headers, "join_groups", {"count": 2, "filters": {"status_keyword": GROUP_KEYWORD_JOIN}}, user.id)
    
    await asyncio.sleep(5)
    final_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    assert final_data['count'] >= initial_count + 2

async def test_leave_groups(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    user, headers = authorized_user_and_headers
    initial_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    initial_count = initial_data['count'] if initial_data else 0
    
    await run_and_verify_task(async_client, db_session, headers, "leave_groups", {"count": 3, "filters": {"status_keyword": GROUP_KEYWORD_LEAVE}}, user.id)
    
    await asyncio.sleep(5)
    final_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    assert final_data['count'] <= initial_count - 3
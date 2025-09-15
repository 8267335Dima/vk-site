# backend/tests/test_group_tasks.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task

pytestmark = pytest.mark.asyncio

GROUP_KEYWORD_JOIN = "python"
GROUP_KEYWORD_LEAVE = "memes"

@pytest.fixture(scope="module", autouse=True)
async def prepare_group_environment(vk_api_client: VKAPI):
    """Вступает в группу, чтобы было из чего выходить в тесте."""
    print(f"\n[PREP] Подготовка среды для тестов групп...")
    groups = await vk_api_client.search_groups(query=GROUP_KEYWORD_LEAVE, count=3)
    group_ids_to_join = [g['id'] for g in groups['items']]
    
    for group_id in group_ids_to_join:
        await vk_api_client.join_group(group_id)
    print(f"[PREP] ✓ Вступили в {len(group_ids_to_join)} группы по слову '{GROUP_KEYWORD_LEAVE}' для теста на выход.")
    
    yield
    
    print(f"\n[CLEANUP] Очистка после тестов групп...")
    joined_groups = await vk_api_client.search_groups(query=GROUP_KEYWORD_JOIN, count=2)
    for group in joined_groups['items']:
        await vk_api_client.leave_group(group['id'])
    print(f"[CLEANUP] ✓ Покинули группы по слову '{GROUP_KEYWORD_JOIN}'.")

async def test_join_groups(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    user, headers = authorized_user_and_headers
    initial_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    initial_count = initial_data['count']
    print(f"[PREP] Текущее количество групп: {initial_count}")
    
    join_count = 2
    payload = {"count": join_count, "filters": {"status_keyword": GROUP_KEYWORD_JOIN}}
    await run_and_verify_task(async_client, db_session, headers, "join_groups", payload, user.id)
    
    print("[VERIFY] Пауза 5 секунд...")
    await asyncio.sleep(5)
    
    final_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    final_count = final_data['count']
    print(f"[VERIFY] Количество групп после вступления: {final_count}")
    
    assert final_count >= initial_count + join_count
    print(f"✓ Проверка 'было/стало' для вступления в группы пройдена ({initial_count} -> {final_count}).")

async def test_leave_groups(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI):
    user, headers = authorized_user_and_headers
    initial_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    initial_count = initial_data['count']
    print(f"[PREP] Текущее количество групп: {initial_count}")
    
    leave_count = 3
    payload = {"count": leave_count, "filters": {"status_keyword": GROUP_KEYWORD_LEAVE}}
    await run_and_verify_task(async_client, db_session, headers, "leave_groups", payload, user.id)
    
    print("[VERIFY] Пауза 5 секунд...")
    await asyncio.sleep(5)
    
    final_data = await vk_api_client.get_groups(user.vk_id, extended=0)
    final_count = final_data['count']
    print(f"[VERIFY] Количество групп после выхода: {final_count}")
    
    assert final_count <= initial_count - leave_count
    print(f"✓ Проверка 'было/стало' для выхода из групп пройдена ({initial_count} -> {final_count}).")
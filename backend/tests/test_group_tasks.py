# backend/tests/test_group_tasks.py
import pytest
import pytest_asyncio
import asyncio
import re
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task

# --- Константы для выполнения задач ---
KEYWORD_JOIN = "Аниме"
KEYWORD_LEAVE = "anime"
ACTION_COUNT = 2


def get_completed_count_from_logs(logs: list[str]) -> int:
    """Извлекает число из финального лога задачи."""
    log_text = "".join(logs)
    match = re.search(r":\s*(\d+)\.", log_text)
    return int(match.group(1)) if match else 0

@pytest.mark.asyncio
async def test_join_groups_by_keyword(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple[User, dict], vk_api_client: VKAPI):
    """
    Тестирует вступление в группы по ключевому слову 'Аниме'.
    """
    user, headers = authorized_user_and_headers
    
    initial_data = await vk_api_client.groups.get(user_id=user.vk_id, extended=0)
    initial_count = initial_data['count'] if initial_data else 0
    print(f"\n[INIT] Исходное количество групп: {initial_count}")

    task_history = await run_and_verify_task(
        async_client, db_session, headers, "join_groups", 
        {"count": ACTION_COUNT, "filters": {"status_keyword": KEYWORD_JOIN}}, user
    )
    
    assert task_history.status == "SUCCESS"
    
    actually_joined_count = get_completed_count_from_logs(task_history.emitter.logs)
    print(f"[VERIFY-JOIN] Из логов извлечено: реально вступлено в {actually_joined_count} групп.")
    assert actually_joined_count > 0, f"Не удалось вступить ни в одну группу по слову '{KEYWORD_JOIN}'. Убедитесь, что вы еще не состоите в популярных открытых группах по этой теме."

    await asyncio.sleep(4)
    final_data = await vk_api_client.groups.get(user_id=user.vk_id, extended=0)
    final_count = final_data['count'] if final_data else 0
    
    assert final_count == initial_count + actually_joined_count, \
        f"Ожидалось {initial_count + actually_joined_count} групп, а по факту {final_count}"


@pytest.mark.asyncio
async def test_leave_groups_by_keyword(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple[User, dict], vk_api_client: VKAPI):
    """
    Тестирует выход из групп по ключевому слову 'anime'.
    Этот тест предполагает, что пользователь УЖЕ состоит в нужных группах.
    """
    user, headers = authorized_user_and_headers
    
    initial_data = await vk_api_client.groups.get(user_id=user.vk_id, extended=0)
    initial_count = initial_data['count'] if initial_data else 0
    print(f"\n[INIT] Количество групп перед выходом: {initial_count}")
    
    task_history = await run_and_verify_task(
        async_client, db_session, headers, "leave_groups", 
        {"count": ACTION_COUNT, "filters": {"status_keyword": KEYWORD_LEAVE}}, user
    )
    
    assert task_history.status == "SUCCESS"
    
    actually_left_count = get_completed_count_from_logs(task_history.emitter.logs)
    print(f"[VERIFY-LEAVE] Из логов извлечено: реально покинуто {actually_left_count} групп.")
    assert actually_left_count > 0, "Не удалось выйти ни из одной группы. Убедитесь, что аккаунт состоит в группах по ключевому слову 'anime'."

    await asyncio.sleep(4)
    final_data = await vk_api_client.groups.get(user_id=user.vk_id, extended=0)
    final_count = final_data['count'] if final_data else 0

    assert final_count == initial_count - actually_left_count, \
        f"Ожидалось {initial_count - actually_left_count} групп, а по факту {final_count}"
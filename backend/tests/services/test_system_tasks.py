# tests/tasks/test_system_tasks.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock
from datetime import datetime, timedelta, UTC

from app.db.models import User, ScheduledPost, ScheduledPostStatus
from app.tasks.system_tasks import publish_scheduled_post_task

pytestmark = pytest.mark.anyio

@pytest.fixture
def mock_arq_context(mocker):
    """Мокает контекст, который ARQ передает в задачу."""
    return {"redis_pool": AsyncMock()}

async def test_publish_scheduled_post_task_success(
    db_session: AsyncSession, test_user: User, mock_arq_context, mocker
):
    """
    Тест на успешное выполнение задачи по публикации отложенного поста.
    """
    post = ScheduledPost(
        user_id=test_user.id,
        vk_profile_id=test_user.vk_id,
        post_text="Тестовый пост для публикации",
        status=ScheduledPostStatus.scheduled,
        publish_at=datetime.now(UTC) - timedelta(minutes=1)
    )
    db_session.add(post)
    await db_session.flush()

    # --- НАЧАЛО ИЗМЕНЕНИЯ ---
    mock_vk_api_class = mocker.patch('app.tasks.system_tasks.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    
    # Теперь wall.post - это асинхронный мок, который возвращает наш словарь
    mock_instance.wall.post = AsyncMock(return_value={"post_id": 987})
    
    mock_instance.close = AsyncMock()
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    
    await publish_scheduled_post_task(
        mock_arq_context, post_id=post.id, db_session_for_test=db_session
    )

    await db_session.refresh(post)
    assert post.status == ScheduledPostStatus.published
    assert post.vk_post_id == "987"
    assert post.error_message is None
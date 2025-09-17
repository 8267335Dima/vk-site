# tests/e2e/test_post_lifecycle.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock
from datetime import datetime, timedelta, UTC
from app.services.vk_api import VKAPIError
from app.db.models import User, ScheduledPost, ScheduledPostStatus, Notification 
from app.tasks.system_tasks import publish_scheduled_post_task

pytestmark = pytest.mark.anyio

@pytest.fixture
def mock_arq_context(mocker):
    """Мокает контекст, который ARQ передает в задачу."""
    return {"redis_pool": AsyncMock()}

async def test_post_publishing_and_history_e2e(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    mock_arq_context: dict,
    mocker
):
    """
    E2E Тест:
    1. Создаем отложенный пост в БД.
    2. Имитируем запуск ARQ-задачи для его публикации.
    3. Проверяем, что пост в БД сменил статус на 'published'.
    4. Делаем запрос к API /api/v1/notifications и проверяем, что там появилось
       уведомление об успешной публикации.
    """
    # Arrange:
    post = ScheduledPost(
        user_id=test_user.id,
        vk_profile_id=test_user.vk_id,
        post_text="E2E Test Post",
        status=ScheduledPostStatus.scheduled,
        publish_at=datetime.now(UTC) - timedelta(minutes=5)
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    mock_vk_api_class = mocker.patch('app.tasks.system_tasks.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    mock_instance.wall.post = AsyncMock(return_value={"post_id": 12345})
    mock_instance.close = AsyncMock()

    mock_emitter_class = mocker.patch('app.tasks.system_tasks.RedisEventEmitter')
    mock_emitter_instance = mock_emitter_class.return_value
    
    async def fake_send_notification(session, message, level):
        notification = Notification(user_id=test_user.id, message=message, level=level)
        session.add(notification)
        await session.flush()

    mock_emitter_instance.send_system_notification = AsyncMock(side_effect=fake_send_notification)

    # Act:
    await publish_scheduled_post_task(mock_arq_context, post_id=post.id, db_session_for_test=db_session)
    await db_session.commit()

    # Assert (Phase 1):
    await db_session.refresh(post)
    assert post.status == ScheduledPostStatus.published
    assert post.vk_post_id == "12345"

    # Act (Phase 2):
    response = await async_client.get("/api/v1/notifications", headers=auth_headers)

    # Assert (Phase 2):
    assert response.status_code == 200
    data = response.json()
    assert data["unread_count"] == 1
    assert len(data["items"]) == 1
    assert "Запланированный пост успешно опубликован" in data["items"][0]["message"]

async def test_post_publishing_failure_e2e(
    async_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict,
    mock_arq_context: dict,
    mocker
):
    """
    E2E Тест неудачного сценария:
    1. Создаем отложенный пост.
    2. Мокаем VK API так, чтобы он выбросил исключение.
    3. Запускаем ARQ-задачу.
    4. Проверяем, что статус поста 'failed' и есть сообщение об ошибке.
    5. Проверяем, что в API уведомлений пришло сообщение об ошибке.
    """
    # Arrange:
    post = ScheduledPost(
        user_id=test_user.id,
        vk_profile_id=test_user.vk_id,
        post_text="E2E Failing Post",
        status=ScheduledPostStatus.scheduled,
        publish_at=datetime.now(UTC) - timedelta(minutes=5)
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    # Мокаем VK API, чтобы он падал с ошибкой
    mock_vk_api_class = mocker.patch('app.tasks.system_tasks.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    mock_instance.wall.post.side_effect = VKAPIError("Access to posting is denied", 214)
    mock_instance.close = AsyncMock()

    # Мокаем эмиттер так же, как в успешном тесте
    mock_emitter_class = mocker.patch('app.tasks.system_tasks.RedisEventEmitter')
    mock_emitter_instance = mock_emitter_class.return_value
    async def fake_send_notification(session, message, level):
        notification = Notification(user_id=test_user.id, message=message, level=level)
        session.add(notification)
        await session.flush()
    mock_emitter_instance.send_system_notification = AsyncMock(side_effect=fake_send_notification)

    # Act:
    await publish_scheduled_post_task(mock_arq_context, post_id=post.id, db_session_for_test=db_session)
    await db_session.commit()

    # Assert (Phase 1): Проверяем состояние в БД
    await db_session.refresh(post)
    assert post.status == ScheduledPostStatus.failed
    assert "Access to posting is denied" in post.error_message

    # Act (Phase 2): Запрашиваем уведомления через API
    response = await async_client.get("/api/v1/notifications", headers=auth_headers)

    # Assert (Phase 2): Проверяем ответ от API
    assert response.status_code == 200
    data = response.json()
    assert data["unread_count"] == 1
    assert "Ошибка публикации поста: Access to posting is denied" in data["items"][0]["message"]
    assert data["items"][0]["level"] == "error"
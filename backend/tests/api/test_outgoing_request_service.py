# tests/services/test_outgoing_request_service.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.services.outgoing_request_service import OutgoingRequestService
from app.db.models import User
from app.api.schemas.actions import AddFriendsRequest
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserLimitReachedError

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_emitter(mocker) -> RedisEventEmitter:
    mock_redis = AsyncMock()
    emitter = RedisEventEmitter(mock_redis)
    emitter.send_log = mocker.AsyncMock()
    emitter.send_stats_update = mocker.AsyncMock()
    return emitter


async def test_add_friends_no_recommendations(db_session: AsyncSession, test_user: User, mock_emitter: RedisEventEmitter, mocker):
    """
    Тест: что происходит, если VK API не вернул рекомендованных друзей.
    """
    # Arrange
    service = OutgoingRequestService(db=db_session, user=test_user, emitter=mock_emitter)
    mock_vk_api = AsyncMock()
    # Мокаем VK API, чтобы он вернул пустой ответ
    mock_vk_api.get_recommended_friends.return_value = {"items": []}
    service.vk_api = mock_vk_api
    service.humanizer = AsyncMock()

    # Act
    request_params = AddFriendsRequest(count=10)
    await service._add_recommended_friends_logic(request_params)

    # Assert
    # Проверяем, что метод добавления в друзья не был вызван ни разу
    mock_vk_api.add_friend.assert_not_called()
    # Проверяем, что в лог было отправлено соответствующее сообщение
    mock_emitter.send_log.assert_any_call("Рекомендации не найдены.", "warning")


async def test_add_friends_daily_limit_reached(db_session: AsyncSession, test_user: User, mock_emitter: RedisEventEmitter, mocker):
    """
    Тест: задача должна остановиться с ошибкой, если достигнут дневной лимит.
    """
    # Arrange: Устанавливаем лимит пользователя на 0
    test_user.daily_add_friends_limit = 0
    await db_session.merge(test_user)
    await db_session.commit()

    service = OutgoingRequestService(db=db_session, user=test_user, emitter=mock_emitter)
    mock_vk_api = AsyncMock()
    mock_vk_api.get_recommended_friends.return_value = {"items": [{"id": 123}]} # Возвращаем одного рекомендованного
    service.vk_api = mock_vk_api
    service.humanizer = AsyncMock()

    # Act & Assert: Ожидаем, что будет вызвано исключение UserLimitReachedError
    with pytest.raises(UserLimitReachedError) as excinfo:
        await service._add_recommended_friends_logic(AddFriendsRequest(count=10))

    assert "Достигнут дневной лимит" in str(excinfo.value)
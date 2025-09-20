# tests/services/test_services_isolated.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.services.outgoing_request_service import OutgoingRequestService
from app.db.models import User, DailyStats
from app.api.schemas.actions import AddFriendsRequest, LikeAfterAddConfig
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserLimitReachedError
from app.services.vk_api import VKAccessDeniedError
from redis.asyncio import Redis as AsyncRedis
from app.core.config import settings

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

async def test_add_friends_redis_lock_prevents_duplicates(
    db_session: AsyncSession, test_user: User, mock_emitter: RedisEventEmitter, mocker
):
    """
    Тест проверяет, что Redis-блокировка внутри сервиса предотвращает
    повторную отправку заявки в друзья одному и тому же человеку.
    """
    # Arrange
    service = OutgoingRequestService(db=db_session, user=test_user, emitter=mock_emitter)
    mock_vk_api = AsyncMock()
    # VK API возвращает двух одинаковых людей в рекомендациях
    mock_vk_api.get_recommended_friends.return_value = {
        "items": [
            {"id": 123, "first_name": "Duplicate"},
            {"id": 123, "first_name": "Duplicate"}
        ]
    }
    mock_vk_api.add_friend.return_value = 1
    service.vk_api = mock_vk_api
    service.humanizer = AsyncMock()
    
    # Очистим тестовый Redis перед запуском.
    redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2")
    await redis_client.flushdb()
    await redis_client.aclose()

    # Act
    request_params = AddFriendsRequest(count=10)
    await service._add_recommended_friends_logic(request_params)

    # Assert
    # Ключевая проверка: несмотря на двух одинаковых людей в ответе VK,
    # реальный вызов API для отправки заявки должен быть только один.
    mock_vk_api.add_friend.assert_called_once_with(123, None)

async def test_add_friends_with_liking_closed_profile(
    db_session: AsyncSession, test_user: User, mock_emitter: RedisEventEmitter, mocker
):
    """
    Тест: проверяет, что при добавлении в друзья пользователя с закрытым
    профилем, сервис не пытается ставить лайки, а сообщает об этом в лог.
    """
    # Arrange
    service = OutgoingRequestService(db=db_session, user=test_user, emitter=mock_emitter)
    mock_vk_api = AsyncMock()
    mock_vk_api.get_recommended_friends.return_value = {"items": [{"id": 123, "is_closed": True, "first_name": "Закрытый"}]}
    mock_vk_api.add_friend.return_value = 1
    service.vk_api = mock_vk_api
    service.humanizer = AsyncMock()
    mocker.patch('app.services.outgoing_request_service.AsyncRedis.from_url').return_value = AsyncMock()

    request_params = AddFriendsRequest(count=1, like_config=LikeAfterAddConfig(enabled=True))

    # Act
    await service._add_recommended_friends_logic(request_params)

    # Assert
    mock_vk_api.add_friend.assert_called_once()
    mock_vk_api.add_like.assert_not_called()
    
    mock_emitter.send_log.assert_any_call(
        "Профиль Закрытый закрыт, пропуск лайкинга.", "info", target_url="https://vk.com/id123"
    )

async def test_add_friends_with_message_limit_reached_mid_task(
    db_session: AsyncSession, test_user: User, mock_emitter: RedisEventEmitter, mocker
):
    """
    Тест: если во время добавления друзей с приветственным сообщением
    заканчивается лимит на сообщения, заявки продолжают отправляться, но без текста.
    """
    # Arrange
    test_user.daily_message_limit = 1 # Лимит всего на 1 сообщение
    stats = DailyStats(user_id=test_user.id, friends_added_count=0, messages_sent_count=0)
    db_session.add_all([test_user, stats])
    await db_session.commit()

    service = OutgoingRequestService(db=db_session, user=test_user, emitter=mock_emitter)
    mock_vk_api = AsyncMock()
    mock_vk_api.get_recommended_friends.return_value = {
        "items": [
            {"id": 101, "first_name": "Первый"},
            {"id": 102, "first_name": "Второй"}
        ]
    }
    mock_vk_api.add_friend.return_value = 1
    service.vk_api = mock_vk_api
    service.humanizer = AsyncMock()
    mocker.patch('app.services.outgoing_request_service.AsyncRedis.from_url').return_value = AsyncMock()

    request_params = AddFriendsRequest(count=2, send_message_on_add=True, message_text="Привет, {name}!")

    # Act
    await service._add_recommended_friends_logic(request_params)

    # Assert
    assert mock_vk_api.add_friend.call_count == 2
    
    calls = mock_vk_api.add_friend.call_args_list
    assert calls[0].args[0] == 101
    assert calls[0].args[1] == "Привет, Первый!" # Сообщение для первого
    assert calls[1].args[0] == 102
    assert calls[1].args[1] is None # Для второго сообщения уже нет

    # Проверяем, что в лог было отправлено предупреждение
    mock_emitter.send_log.assert_any_call(
        "Достигнут лимит сообщений. Заявка для Второй будет отправлена без приветствия.", "warning"
    )
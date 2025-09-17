# tests/services/test_friend_management_service.py
import pytest
from unittest.mock import AsyncMock

from app.services.friend_management_service import FriendManagementService
from app.api.schemas.actions import RemoveFriendsRequest, ActionFilters
from app.db.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.event_emitter import RedisEventEmitter # Нужен для инициализации

pytestmark = pytest.mark.anyio

# Пример данных от VK API
MOCK_FRIENDS_DATA = {
    "count": 5,
    "items": [
        {"id": 1, "first_name": "Banned", "last_name": "User", "deactivated": "banned"},
        {"id": 2, "first_name": "Deleted", "last_name": "User", "deactivated": "deleted"},
        {"id": 3, "first_name": "Active", "last_name": "User"}, # Активный, пройдет все фильтры
        {"id": 4, "first_name": "Inactive", "last_name": "User", "last_seen": {"time": 1609459200}}, # Давно не заходил
        {"id": 5, "first_name": "Recent", "last_name": "User", "last_seen": {"time": 9999999999}}, # Заходил недавно
    ]
}

@pytest.fixture
def mock_emitter(mocker) -> RedisEventEmitter:
    """Фикстура для мока эмиттера событий."""
    mock_redis = AsyncMock()
    emitter = RedisEventEmitter(mock_redis)
    # Мокаем методы, чтобы они ничего не делали, но их можно было проверить
    emitter.send_log = mocker.AsyncMock()
    return emitter


async def test_get_remove_friends_targets_logic(
    db_session: AsyncSession, test_user: User, mock_emitter: RedisEventEmitter, mocker
):
    """
    Тестирует логику отбора кандидатов на удаление в изоляции.
    """
    # 1. Arrange: Настраиваем окружение
    service = FriendManagementService(db=db_session, user=test_user, emitter=mock_emitter)

    # Мокаем VK API, чтобы он не делал реальных запросов
    mock_vk_api = AsyncMock()
    mock_vk_api.get_user_friends.return_value = MOCK_FRIENDS_DATA
    service.vk_api = mock_vk_api # Внедряем мок в сервис

    # Параметры задачи: удалить забаненных и тех, кто не заходил > 30 дней
    request_params = RemoveFriendsRequest(
        count=10, filters=ActionFilters(remove_banned=True, last_seen_days=30)
    )

    # 2. Act: Вызываем тестируемый метод
    targets = await service.get_remove_friends_targets(request_params)

    # 3. Assert: Проверяем результат
    # Мы ожидаем, что сервис вернет 3х пользователей: забаненного, удаленного и давно неактивного
    assert len(targets) == 3
    
    target_ids = {t["id"] for t in targets}
    assert target_ids == {1, 2, 4}
    
    # Проверяем, что забаненные идут первыми в списке на удаление
    assert targets[0]["id"] == 1
    assert targets[1]["id"] == 2
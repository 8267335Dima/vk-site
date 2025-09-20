# tests/core/test_main_logic.py

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.main import _check_user_status_and_proceed
from app.api.dependencies import get_request_identifier

pytestmark = pytest.mark.anyio

class TestUserActivityMiddleware:

    @pytest.fixture
    def mock_request_with_redis(self, mock_redis: AsyncMock):
        """Создает мок Request с моком Redis в состоянии приложения."""
        request = MagicMock()
        request.app.state.activity_redis = mock_redis
        return request

    async def test_updates_activity_if_redis_cache_is_missing(
        self, db_session, test_user, mock_request_with_redis, mocker
    ):
        """
        Тест: если в Redis нет записи о последней активности,
        функция должна обновить `last_active_at` в БД и создать запись в Redis.
        """
        # Arrange
        mock_redis = mock_request_with_redis.app.state.activity_redis
        mock_redis.get.return_value = None # Redis ничего не знает об активности
        
        mock_db_execute = mocker.patch.object(db_session, "execute", new_callable=AsyncMock)
        mock_db_commit = mocker.patch.object(db_session, "commit", new_callable=AsyncMock)
        
        mock_get_payload = mocker.patch("app.main.get_token_payload", return_value={})
        mocker.patch("app.main.get_current_active_profile", return_value=test_user)

        # Act
        await _check_user_status_and_proceed(db_session, mock_request_with_redis, AsyncMock(), "Bearer token")

        # Assert
        mock_db_execute.assert_awaited_once() # Был вызов для UPDATE User ...
        mock_db_commit.assert_awaited_once()
        mock_redis.set.assert_awaited_once() # Была создана запись в Redis

    async def test_skips_activity_update_if_redis_cache_is_fresh(
        self, db_session, test_user, mock_request_with_redis, mocker
    ):
        """
        Тест: если в Redis есть "свежая" запись об активности (меньше 60 сек),
        функция НЕ должна обращаться к БД и обновлять Redis.
        """
        # Arrange
        import time
        mock_redis = mock_request_with_redis.app.state.activity_redis
        mock_redis.get.return_value = time.time() - 30 # Активность была 30 секунд назад

        mock_db_execute = mocker.patch.object(db_session, "execute", new_callable=AsyncMock)
        mock_db_commit = mocker.patch.object(db_session, "commit", new_callable=AsyncMock)
        
        mocker.patch("app.main.get_token_payload", return_value={})
        mocker.patch("app.main.get_current_active_profile", return_value=test_user)

        # Act
        await _check_user_status_and_proceed(db_session, mock_request_with_redis, AsyncMock(), "Bearer token")

        # Assert
        mock_db_execute.assert_not_awaited()
        mock_db_commit.assert_not_awaited()
        mock_redis.set.assert_not_awaited()

class TestRateLimiterIdentifier:

    async def test_get_identifier_with_forwarded_header(self):
        """Тест: идентификатор должен браться из заголовка X-Forwarded-For."""
        mock_request = MagicMock(
            headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"},
            client=MagicMock(host="9.9.9.9")
        )
        identifier = await get_request_identifier(mock_request)
        assert identifier == "1.2.3.4"

    async def test_get_identifier_without_forwarded_header(self):
        """Тест: при отсутствии заголовка используется IP клиента."""
        mock_request = MagicMock(
            headers={},
            client=MagicMock(host="9.9.9.9")
        )
        identifier = await get_request_identifier(mock_request)
        assert identifier == "9.9.9.9"
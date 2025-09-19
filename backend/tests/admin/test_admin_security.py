import pytest
from unittest.mock import AsyncMock
import jwt

from app.admin.auth import AdminAuth
from app.core.config import settings

ASYNC_TEST = pytest.mark.asyncio

@pytest.fixture
def auth_backend():
    return AdminAuth(secret_key=settings.SECRET_KEY)

class TestAdminTokenAuthentication:

    @ASYNC_TEST
    async def test_authenticate_success(self, auth_backend: AdminAuth):
        """Проверяет успешную аутентификацию с валидным токеном."""
        token_payload = {"sub": settings.ADMIN_USER, "scope": "admin_access"}
        token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        mock_request = AsyncMock(session={"token": token})
        
        assert await auth_backend.authenticate(mock_request) is True

    @ASYNC_TEST
    async def test_authenticate_no_token(self, auth_backend: AdminAuth):
        """Проверяет провал аутентификации, если токена нет в сессии."""
        mock_request = AsyncMock(session={})
        assert await auth_backend.authenticate(mock_request) is False

    @ASYNC_TEST
    async def test_authenticate_wrong_scope(self, auth_backend: AdminAuth):
        """Проверяет провал, если у токена неверный scope (например, от impersonate)."""
        token_payload = {"sub": "some_user", "scope": "impersonate"} # Неверный scope
        token = jwt.encode(token_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        mock_request = AsyncMock(session={"token": token})
        assert await auth_backend.authenticate(mock_request) is False

    @ASYNC_TEST
    async def test_authenticate_bad_signature(self, auth_backend: AdminAuth):
        """Проверяет провал, если токен подписан неверным ключом."""
        token_payload = {"sub": settings.ADMIN_USER, "scope": "admin_access"}
        # Подписываем другим ключом
        bad_token = jwt.encode(token_payload, "wrong-secret-key", algorithm=settings.ALGORITHM)

        mock_request = AsyncMock(session={"token": bad_token})
        assert await auth_backend.authenticate(mock_request) is False


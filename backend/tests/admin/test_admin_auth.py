import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession # <--- Импорт

from app.admin.auth import AdminAuth
from app.db.models import User
from app.core.config import settings

ASYNC_TEST = pytest.mark.asyncio

@pytest.fixture
def auth_backend():
    return AdminAuth(secret_key="test-secret")

class TestAdminAuthentication:

    @ASYNC_TEST
    async def test_login_successful(self, auth_backend: AdminAuth, admin_user: User, db_session: AsyncSession): # <--- Добавлена db_session
        """Проверяет успешный вход, когда все условия выполнены."""
        mock_request = AsyncMock()
        mock_request.session = {}
        mock_request.state.session = db_session # <--- ИСПРАВЛЕНО

        async def form():
            return {"username": settings.ADMIN_USER, "password": settings.ADMIN_PASSWORD}
        mock_request.form = form
        
        result = await auth_backend.login(mock_request)

        assert result is True
        assert "token" in mock_request.session

    @ASYNC_TEST
    async def test_login_wrong_credentials(self, auth_backend: AdminAuth):
        """Проверяет отказ при неверном логине/пароле."""
        mock_request = AsyncMock()
        async def form():
            return {"username": "wrong_user", "password": "wrong_password"}
        mock_request.form = form

        result = await auth_backend.login(mock_request)
        assert result is False

    @ASYNC_TEST
    async def test_login_admin_user_not_in_db(self, auth_backend: AdminAuth, db_session: AsyncSession):
        """Проверяет отказ, если админа нет в таблице User."""
        mock_request = AsyncMock()
        mock_request.state.session = db_session
        async def form():
            return {"username": settings.ADMIN_USER, "password": settings.ADMIN_PASSWORD}
        mock_request.form = form
        
        # ИСПРАВЛЕННЫЙ ЗАПРОС
        stmt = select(User).where(User.vk_id == int(settings.ADMIN_VK_ID))
        users_to_delete = await db_session.execute(stmt)
        for user in users_to_delete.scalars():
            await db_session.delete(user)
        await db_session.commit()

        result = await auth_backend.login(mock_request)
        assert result is False

    @ASYNC_TEST
    async def test_login_user_exists_but_not_admin(self, auth_backend: AdminAuth, admin_user: User, db_session: AsyncSession): # <--- Добавлена db_session
        """Проверяет отказ, если пользователь в БД не имеет флага is_admin."""
        admin_user.is_admin = False
        db_session.add(admin_user)
        await db_session.commit()

        mock_request = AsyncMock()
        mock_request.state.session = db_session # <--- ИСПРАВЛЕНО
        async def form():
            return {"username": settings.ADMIN_USER, "password": settings.ADMIN_PASSWORD}
        mock_request.form = form
        
        result = await auth_backend.login(mock_request)
        assert result is False
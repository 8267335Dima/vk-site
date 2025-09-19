# tests/admin/test_admin_user_actions.py
import json
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock
from datetime import datetime, timezone

from app.admin.views.management.user import UserAdmin
from app.db.models import User

ASYNC_TEST = pytest.mark.asyncio

class TestUserAdminComplexActions:

    @ASYNC_TEST
    async def test_soft_delete_action(self, db_session: AsyncSession, test_user: User, admin_user: User):
        """Проверяет, что soft_delete корректно устанавливает флаги."""
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        assert not test_user.is_deleted
        assert test_user.deleted_at is None
        assert not test_user.is_frozen

        await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)

        assert test_user.is_deleted is True
        assert test_user.deleted_at is not None
        assert isinstance(test_user.deleted_at, datetime)
        assert test_user.is_frozen is True

    @ASYNC_TEST
    async def test_restore_action(self, db_session: AsyncSession, test_user: User):
        """Проверяет, что restore возвращает пользователя в активное состояние."""
        # Сначала "удаляем" пользователя
        test_user.is_deleted = True
        test_user.is_frozen = True
        test_user.deleted_at = datetime.now(timezone.utc)
        db_session.add(test_user)
        await db_session.commit()

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        await admin_view.restore.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)

        assert test_user.is_deleted is False
        assert test_user.deleted_at is None
        assert test_user.is_frozen is False

    @ASYNC_TEST
    async def test_impersonate_with_multiple_pks_fails(self, db_session: AsyncSession, test_user: User):
        """Проверяет, что impersonate возвращает ошибку, если выбрано >1 пользователя."""
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        # pks содержит два ID
        response = await admin_view.impersonate.__wrapped__(admin_view, mock_request, pks=[test_user.id, test_user.id + 1])
        
        assert response.status_code == 400
        response_data = json.loads(response.body)
        assert "Выберите одного пользователя" in response_data["message"]
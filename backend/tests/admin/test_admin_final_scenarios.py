# tests/admin/test_admin_final_scenarios.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock

from app.admin.views.management.user import UserAdmin
from app.db.models import User

ASYNC_TEST = pytest.mark.asyncio

class TestUserAdminFinalScenarios:

    @ASYNC_TEST
    async def test_soft_delete_already_deleted_user_is_idempotent(self, db_session: AsyncSession, test_user: User, admin_user: User):
        """
        Проверяет, что повторное 'мягкое удаление' уже удаленного пользователя
        не вызывает ошибок и не меняет его состояние (идемпотентность).
        """
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        # Первое удаление
        await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)
        first_deletion_time = test_user.deleted_at
        assert test_user.is_deleted is True

        # Второе удаление
        await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)

        # Время удаления не должно было измениться
        assert test_user.deleted_at == first_deletion_time

    @ASYNC_TEST
    async def test_on_model_change_with_empty_token(self, test_user: User):
        """
        Проверяет, что хук on_model_change в UserAdmin не меняет токен пользователя,
        если в форме поле для нового токена было оставлено пустым.
        """
        admin_view = UserAdmin()
        initial_encrypted_token = test_user.encrypted_vk_token
        
        # Симулируем данные формы, где поле для нового токена пустое
        form_data = {"encrypted_vk_token_clear": ""}
        
        await admin_view.on_model_change(data=form_data, model=test_user, is_created=False, request=MagicMock())
        
        # Убеждаемся, что токен остался прежним
        assert test_user.encrypted_vk_token == initial_encrypted_token
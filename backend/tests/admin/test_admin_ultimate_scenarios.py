# tests/admin/test_admin_ultimate_scenarios.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.admin.views.management.user import UserAdmin
from app.admin.views.system.admin_actions import AdminActionsView
from app.db.models import User, Automation

ASYNC_TEST = pytest.mark.asyncio

class TestAdminSafetyAndRobustness:

    @ASYNC_TEST
    async def test_admin_cannot_soft_delete_self(self, db_session: AsyncSession, admin_user: User):
        """Проверяет, что админ не может 'мягко удалить' самого себя."""
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        response = await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[admin_user.id])
        
        assert response.status_code == 400
        assert "Нельзя удалить главного администратора" in response.body.decode()

        await db_session.refresh(admin_user)
        assert not admin_user.is_deleted

    @ASYNC_TEST
    async def test_actions_with_empty_pks_list(self, db_session: AsyncSession, mocker, admin_user: User):
        """Проверяет, что действия не падают и ничего не делают, если список pks пуст."""
        commit_mock = mocker.patch.object(db_session, "commit", new_callable=AsyncMock)

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[])
        await admin_view.restore.__wrapped__(admin_view, mock_request, pks=[])
        await admin_view.toggle_freeze.__wrapped__(admin_view, mock_request, pks=[])
        await admin_view.toggle_shadow_ban.__wrapped__(admin_view, mock_request, pks=[])

        commit_mock.assert_not_awaited()

    @ASYNC_TEST
    async def test_admin_cannot_remove_own_admin_rights(self, db_session: AsyncSession, admin_user: User):
        """Проверяет, что админ не может снять с себя флаг is_admin через форму."""
        admin_view = UserAdmin()
        
        form_data = {"is_admin": False}
        
        with pytest.raises(HTTPException) as excinfo:
            await admin_view.on_model_change(data=form_data, model=admin_user, is_created=False, request=MagicMock())
        
        assert excinfo.value.status_code == 400
        assert "Нельзя снять права с главного администратора" in excinfo.value.detail

    @ASYNC_TEST
    async def test_batch_action_with_one_invalid_pk(self, db_session: AsyncSession, test_user: User):
        """
        Проверяет, что пакетное действие успешно обработает существующих пользователей,
        проигнорировав несуществующий ID в списке, и не упадет.
        """
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        initial_frozen_state = test_user.is_frozen
        non_existent_id = 999999
        
        await admin_view.toggle_freeze.__wrapped__(admin_view, mock_request, pks=[test_user.id, non_existent_id])

        await db_session.refresh(test_user)
        assert test_user.is_frozen is not initial_frozen_state

    @ASYNC_TEST
    async def test_extend_subscription_for_user_with_no_expiry(self, db_session: AsyncSession, admin_user: User):
        """
        Проверяет, что при попытке продлить подписку пользователю
        с вечной подпиской (plan_expires_at=None), дата не изменяется.
        """
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        assert admin_user.plan_expires_at is None

        await admin_view.extend_subscription.__wrapped__(admin_view, mock_request, pks=[admin_user.id])

        await db_session.refresh(admin_user)
        assert admin_user.plan_expires_at is None

    @ASYNC_TEST
    async def test_soft_delete_already_deleted_user_is_idempotent(self, db_session: AsyncSession, test_user: User, admin_user: User):
        """
        Проверяет, что повторное 'мягкое удаление' уже удаленного пользователя
        не вызывает ошибок и не меняет его состояние (идемпотентность).
        """
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)
        first_deletion_time = test_user.deleted_at
        assert test_user.is_deleted is True

        await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)

        assert test_user.deleted_at == first_deletion_time

    @ASYNC_TEST
    async def test_panic_button_resilience_if_arq_fails(self, db_session: AsyncSession, test_user: User, mock_arq_pool: AsyncMock, mocker):
        """
        Тест на отказоустойчивость: "тревожная кнопка" должна заморозить
        пользователей и автоматизации, даже если ARQ недоступен и
        метод abort_job выбрасывает исключение.
        """
        mocker.patch("app.admin.auth.AdminAuth.authenticate", return_value=True)
        automation = Automation(user_id=test_user.id, automation_type="LIKE_FEED", is_active=True)
        test_user.is_frozen = False
        db_session.add_all([automation, test_user])
        await db_session.commit()

        mock_arq_pool.all_jobs = AsyncMock(return_value=[MagicMock(job_id="fail_job")])
        mock_arq_pool.abort_job.side_effect = Exception("ARQ connection error")

        mock_request = AsyncMock(
            method="POST",
            state=MagicMock(session=db_session),
            app=MagicMock(state=MagicMock(arq_pool=mock_arq_pool)),
            form=AsyncMock(return_value={"panic_button": "true"})
        )
        admin_view = AdminActionsView()
        admin_view.templates = MagicMock()
        
        await admin_view.actions_page(mock_request)
        
        await db_session.refresh(automation)
        assert automation.is_active is False
        await db_session.refresh(test_user)
        assert test_user.is_frozen is True

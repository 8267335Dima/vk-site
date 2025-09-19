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
    async def test_admin_cannot_remove_own_admin_rights(self, db_session: AsyncSession, admin_user: User):
        """Проверяет, что админ не может снять с себя флаг is_admin через форму."""
        admin_view = UserAdmin()
        
        # Симулируем данные из формы, где флаг is_admin снят
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
        
        # Выполняем действие со смешанным списком ID
        await admin_view.toggle_freeze.__wrapped__(admin_view, mock_request, pks=[test_user.id, non_existent_id])

        await db_session.refresh(test_user)
        # Убеждаемся, что существующий пользователь был обработан
        assert test_user.is_frozen is not initial_frozen_state

    @ASYNC_TEST
    async def test_panic_button_when_no_jobs_exist(self, db_session: AsyncSession, mock_arq_pool: MagicMock, mocker):
        """Проверяет, что "тревожная кнопка" работает, даже если в ARQ нет активных задач."""
        mocker.patch("app.admin.auth.AdminAuth.authenticate", return_value=True)
        # ARQ pool возвращает пустой список задач
        mock_arq_pool.all_jobs = AsyncMock(return_value=[])
        
        mock_request = AsyncMock(
            method="POST",
            state=MagicMock(session=db_session),
            app=MagicMock(state=MagicMock(arq_pool=mock_arq_pool)),
            form=AsyncMock(return_value={"panic_button": "true"})
        )
        admin_view = AdminActionsView()
        admin_view.templates = MagicMock()
        admin_view.templates.TemplateResponse.return_value = "OK"

        # Ожидаем, что код выполнится без ошибок
        await admin_view.actions_page(mock_request)
        
        # Проверяем, что abort_job не вызывался
        mock_arq_pool.abort_job.assert_not_called()
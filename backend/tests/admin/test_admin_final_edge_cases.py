# tests/admin/test_admin_final_edge_cases.py

import pytest
from unittest.mock import MagicMock, AsyncMock

from app.admin.views.management.user import UserAdmin
from app.admin.views.system.admin_actions import AdminActionsView
from app.db.models import User, Automation

ASYNC_TEST = pytest.mark.asyncio

class TestAdminFinalEdgeCases:
    
    @ASYNC_TEST
    async def test_panic_button_happy_path(self, db_session, test_user: User, mock_arq_pool: AsyncMock):
        """
        Проверяет "счастливый путь" для "тревожной кнопки": все зависимости на месте,
        и все действия выполняются корректно.
        """
        # Arrange
        automation = Automation(user_id=test_user.id, automation_type="LIKE_FEED", is_active=True)
        test_user.is_frozen = False
        db_session.add_all([automation, test_user])
        await db_session.commit()

        # Настраиваем мок ARQ
        mock_job = MagicMock()
        mock_job.job_id = "test_job_1"
        mock_arq_pool.all_jobs = AsyncMock(return_value=[mock_job])
        mock_arq_pool.abort_job = AsyncMock()

        # Настраиваем мок Request
        mock_request = AsyncMock(
            method="POST",
            state=MagicMock(session=db_session),
            app=MagicMock(state=MagicMock(arq_pool=mock_arq_pool)),
            form=AsyncMock(return_value={"panic_button": "true"})
        )
        # Мокаем шаблонизатор
        admin_view = AdminActionsView()
        admin_view.templates = MagicMock()
        
        # Act
        await admin_view.actions_page(mock_request)

        # Assert
        # Проверяем, что была вызвана отмена задачи
        mock_arq_pool.abort_job.assert_awaited_once_with("test_job_1")
        
        # Проверяем, что автоматизация и пользователь были заморожены
        await db_session.refresh(automation)
        assert automation.is_active is False
        await db_session.refresh(test_user)
        assert test_user.is_frozen is True

    @ASYNC_TEST
    async def test_main_middleware_handles_token_payload_exception(self, mocker):
        """
        Тест: проверяет, что middleware в main.py корректно пропускает запрос дальше,
        даже если get_token_payload выбрасывает HTTPException.
        """
        from app.main import _check_user_status_and_proceed
        from fastapi import HTTPException

        # Arrange
        mock_call_next = AsyncMock()
        mocker.patch("app.main.get_token_payload", side_effect=HTTPException(status_code=401))

        # Act
        await _check_user_status_and_proceed(
            db=AsyncMock(),
            request=AsyncMock(),
            call_next=mock_call_next,
            token="Bearer invalid"
        )

        # Assert
        # Ключевая проверка: call_next был вызван, то есть middleware не упал,
        # а передал управление дальше FastAPI, который и вернет 401.
        mock_call_next.assert_awaited_once()
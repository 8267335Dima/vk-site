import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import select
import json

from app.admin.views.support.ticket import SupportTicketAdmin
from app.admin.views.system.admin_actions import AdminActionsView
from app.db.models import SupportTicket, TicketStatus, Automation, User

ASYNC_TEST = pytest.mark.asyncio


class TestSupportAdminActions:

    @ASYNC_TEST
    async def test_resolve_tickets_action(self, db_session: AsyncSession, test_user: User):
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.OPEN)
        db_session.add(ticket)
        await db_session.commit()
        
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = SupportTicketAdmin()
        
        await admin_view.resolve_tickets.__wrapped__(admin_view, mock_request, pks=[ticket.id])
        
        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.RESOLVED

    @ASYNC_TEST
    async def test_close_permanently_action(self, db_session: AsyncSession, test_user: User):
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.OPEN)
        db_session.add(ticket)
        await db_session.commit()
        
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = SupportTicketAdmin()
        
        await admin_view.close_permanently.__wrapped__(admin_view, mock_request, pks=[ticket.id])
        
        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.CLOSED


class TestEmergencyActions:

    # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
    # Весь следующий метод сдвинут вправо, чтобы быть частью класса
    @ASYNC_TEST
    async def test_panic_button_action(self, db_session: AsyncSession, test_user: User, mock_arq_pool: AsyncMock, mocker):
        """Проверяет работу "тревожной кнопки", которая останавливает все."""
        mocker.patch("app.admin.auth.AdminAuth.authenticate", return_value=True)

        automation = Automation(user_id=test_user.id, automation_type="LIKE_FEED", is_active=True)
        db_session.add(automation)
        test_user.is_frozen = False
        db_session.add(test_user)
        await db_session.commit()

        mock_job = MagicMock()
        mock_job.job_id = "test_job_1"
        mock_arq_pool.all_jobs = AsyncMock(return_value=[mock_job])
        mock_arq_pool.abort_job = AsyncMock()

        mock_request = AsyncMock()
        mock_request.method = "POST"
        mock_request.state.session = db_session
        mock_request.app.state.arq_pool = mock_arq_pool
        async def form():
            return {"panic_button": "true"}
        mock_request.form = form

        admin_view = AdminActionsView()
        admin_view.templates = MagicMock()
        admin_view.templates.TemplateResponse = MagicMock()
        
        await admin_view.actions_page(mock_request)

        mock_arq_pool.abort_job.assert_awaited_once_with("test_job_1")
        
        await db_session.refresh(automation)
        assert automation.is_active is False

        await db_session.refresh(test_user)
        assert test_user.is_frozen is True
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
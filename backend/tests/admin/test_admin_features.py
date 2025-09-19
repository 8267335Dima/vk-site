import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import MagicMock

from app.admin.views.management.user import UserAdmin
from app.admin.views.support.ticket import SupportTicketAdmin
from app.db.models import User, SupportTicket, TicketStatus, LoginHistory, BannedIP

ASYNC_TEST = pytest.mark.asyncio

class TestUserAdminActions:

    @ASYNC_TEST
    async def test_soft_delete_and_restore_action(self, db_session: AsyncSession, test_user: User):
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        await admin_view.soft_delete(mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)
        assert test_user.is_deleted is True

        await admin_view.restore(mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)
        assert test_user.is_deleted is False

class TestSupportTicketNewActions:

    @ASYNC_TEST
    async def test_resolve_tickets_action(self, db_session: AsyncSession, test_user: User):
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.OPEN)
        db_session.add(ticket)
        await db_session.commit()
        
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = SupportTicketAdmin()
        
        await admin_view.resolve_tickets(mock_request, pks=[ticket.id])
        
        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.RESOLVED

    @ASYNC_TEST
    async def test_close_permanently_action(self, db_session: AsyncSession, test_user: User):
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.OPEN)
        db_session.add(ticket)
        await db_session.commit()

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = SupportTicketAdmin()
        
        await admin_view.close_permanently(mock_request, pks=[ticket.id])
        
        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.CLOSED
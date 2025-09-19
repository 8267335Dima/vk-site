import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock
from datetime import datetime, timezone

from app.admin.views.management.user import UserAdmin
from app.admin.views.system.banned_ip import BannedIPAdmin
from app.admin.views.support.ticket import SupportTicketAdmin
from app.admin.views.monitoring.task_history import TaskHistoryAdmin
from app.db.models import User, BannedIP, SupportTicket, TicketStatus, TaskHistory, Plan

ASYNC_TEST = pytest.mark.asyncio

class TestNewUserAdminActions:

    @ASYNC_TEST
    async def test_toggle_freeze_action(self, db_session: AsyncSession, test_user: User):
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        initial_state = test_user.is_frozen
        await admin_view.toggle_freeze(mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)
        assert test_user.is_frozen is not initial_state

        await admin_view.toggle_freeze(mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)
        assert test_user.is_frozen is initial_state
        
    @ASYNC_TEST
    async def test_toggle_shadow_ban_action(self, db_session: AsyncSession, test_user: User):
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        await admin_view.toggle_shadow_ban(mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)
        assert test_user.is_shadow_banned is True

class TestNewSystemAdminActions:

    @ASYNC_TEST
    async def test_unban_ips_action(self, db_session: AsyncSession, admin_user: User):
        ban = BannedIP(ip_address="3.3.3.3", admin_id=admin_user.id)
        db_session.add(ban)
        await db_session.commit()
        
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = BannedIPAdmin()

        await admin_view.unban_ips(mock_request, pks=[ban.id])
        
        ban_in_db = await db_session.get(BannedIP, ban.id)
        assert ban_in_db is None

class TestNewSupportAdminActions:
    @ASYNC_TEST
    async def test_reopen_tickets_action(self, db_session: AsyncSession, test_user: User):
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.RESOLVED)
        db_session.add(ticket)
        await db_session.commit()
        
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = SupportTicketAdmin()
        
        await admin_view.reopen_tickets(mock_request, pks=[ticket.id])
        
        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.OPEN

class TestNewTaskHistoryAdminActions:
    @ASYNC_TEST
    async def test_mark_as_successful_action(self, db_session: AsyncSession, test_user: User):
        task = TaskHistory(user_id=test_user.id, task_name="Test", status="FAILURE")
        db_session.add(task)
        await db_session.commit()
        
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = TaskHistoryAdmin()

        await admin_view.mark_as_successful(mock_request, pks=[task.id])
        
        await db_session.refresh(task)
        assert task.status == "SUCCESS"
        
    @ASYNC_TEST
    async def test_cancel_manually_action(self, db_session: AsyncSession, test_user: User):
        task = TaskHistory(user_id=test_user.id, task_name="Test", status="SUCCESS")
        db_session.add(task)
        await db_session.commit()

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = TaskHistoryAdmin()
        
        await admin_view.cancel_manually(mock_request, pks=[task.id])
        
        await db_session.refresh(task)
        assert task.status == "CANCELLED"
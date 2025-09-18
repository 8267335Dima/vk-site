# tests/admin/test_admin_features.py

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from app.admin.views.user import UserAdmin
from app.admin.views.support import SupportTicketAdmin
from app.db.models import User, SupportTicket, TicketStatus, LoginHistory, BannedIP
from app.core.constants import PlanName

ASYNC_TEST = pytest.mark.asyncio

class TestUserAdminNewActions:
    @ASYNC_TEST
    async def test_delete_account_action(self):
        mock_session = AsyncMock()
        mock_user = MagicMock(spec=User)
        mock_session.get.return_value = mock_user
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = UserAdmin()

        response = await admin_view.delete_account(mock_request, pks=[1])

        mock_session.delete.assert_awaited_with(mock_user)
        mock_session.commit.assert_awaited_once()
        assert response["message"] == "Удалено аккаунтов: 1"

    @ASYNC_TEST
    async def test_ban_user_ip_action(self):
        mock_session = AsyncMock()
        # Симулируем, что IP в базе есть, но бана еще нет
        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: "192.168.1.1"), # Находим IP
            MagicMock(scalar_one_or_none=lambda: None)           # Проверяем - бана нет
        ]
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = UserAdmin()

        response = await admin_view.ban_user_ip(mock_request, pks=[1])

        # Проверяем, что был вызван add для объекта BannedIP
        assert mock_session.add.call_count == 1
        added_object = mock_session.add.call_args[0][0]
        assert isinstance(added_object, BannedIP)
        assert added_object.ip_address == "192.168.1.1"
        
        mock_session.commit.assert_awaited_once()
        assert response["message"] == "Заблокировано IP-адресов: 1"

    @ASYNC_TEST
    async def test_ban_user_ip_when_already_banned(self):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=lambda: "192.168.1.1"), # Находим IP
            MagicMock(scalar_one_or_none=lambda: MagicMock(spec=BannedIP)) # Проверяем - бан есть
        ]
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = UserAdmin()

        response = await admin_view.ban_user_ip(mock_request, pks=[1])

        mock_session.add.assert_not_called()
        mock_session.commit.assert_awaited_once() # commit все равно вызывается
        assert response["message"] == "Заблокировано IP-адресов: 0"

class TestSupportTicketNewActions:
    @ASYNC_TEST
    async def test_resolve_tickets_action(self):
        mock_session = AsyncMock()
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_session.get.return_value = mock_ticket
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = SupportTicketAdmin()

        await admin_view.resolve_tickets(mock_request, pks=[1])

        assert mock_ticket.status == TicketStatus.RESOLVED
        assert mock_ticket.updated_at is not None
        mock_session.commit.assert_awaited_once()

    @ASYNC_TEST
    async def test_close_permanently_action(self):
        mock_session = AsyncMock()
        mock_ticket = MagicMock(spec=SupportTicket)
        mock_session.get.return_value = mock_ticket
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = SupportTicketAdmin()

        await admin_view.close_permanently(mock_request, pks=[1])

        assert mock_ticket.status == TicketStatus.CLOSED
        assert mock_ticket.updated_at is not None
        mock_session.commit.assert_awaited_once()
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock
from fastapi import HTTPException
from jose import jwt
import json

from app.admin.views.management.user import UserAdmin
from app.api.endpoints.support import reply_to_ticket
from app.db.models import User, SupportTicket, TicketStatus
from app.core.config import settings
from app.services.system_service import SystemService
from app.core.plans import is_feature_available_for_plan
from app.core.security import decrypt_data

ASYNC_TEST = pytest.mark.asyncio

class TestAdminSuperpowers:
    @ASYNC_TEST
    async def test_admin_has_access_to_disabled_feature(self, test_user, admin_user, mocker):
        mocker.patch.object(SystemService, 'is_feature_enabled', return_value=False)
        assert not await is_feature_available_for_plan(test_user.plan.name_id, "any_feature", user=test_user)
        assert await is_feature_available_for_plan(admin_user.plan.name_id, "any_feature", user=admin_user)

    @ASYNC_TEST
    async def test_impersonate_action_creates_correct_token(self, db_session: AsyncSession, admin_user: User, test_user: User):
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        response = await admin_view.impersonate.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        
        assert response.status_code == 200
        
        response_data = json.loads(response.body.decode())
        
        assert "impersonation_token" in response_data
        access_token = response_data["impersonation_token"]

        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        assert payload['sub'] == str(admin_user.id)
        assert payload['profile_id'] == str(test_user.id)
        assert payload['scope'] == 'impersonate'
        
        assert "real_vk_token" in response_data
        decrypted_vk_token = decrypt_data(test_user.encrypted_vk_token)
        assert response_data["real_vk_token"] == decrypted_vk_token


class TestTicketSystemLimits:
    @ASYNC_TEST
    async def test_user_cannot_reopen_ticket_more_than_limit(self, db_session: AsyncSession, test_user: User, mocker):
        mocker.patch.object(SystemService, 'get_ticket_reopen_limit', return_value=1)
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.RESOLVED, reopen_count=1)
        db_session.add(ticket)
        await db_session.commit()
        
        with pytest.raises(HTTPException) as excinfo:
            mock_message_data = MagicMock(message="one more time", attachment_url=None)
            await reply_to_ticket(ticket_id=ticket.id, message_data=mock_message_data, current_user=test_user, db=db_session)
        
        assert excinfo.value.status_code == 403

    @ASYNC_TEST
    async def test_user_can_reopen_ticket_within_limit(self, db_session: AsyncSession, test_user: User, mocker):
        mocker.patch.object(SystemService, 'get_ticket_reopen_limit', return_value=2)
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.RESOLVED, reopen_count=1)
        db_session.add(ticket)
        await db_session.commit()

        mock_message_data = MagicMock(message="I can do this", attachment_url=None)
        await reply_to_ticket(ticket_id=ticket.id, message_data=mock_message_data, current_user=test_user, db=db_session)

        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.OPEN
        assert ticket.reopen_count == 2
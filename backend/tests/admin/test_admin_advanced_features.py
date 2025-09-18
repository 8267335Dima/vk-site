# tests/admin/test_admin_advanced_features.py

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import select # <--- ИСПРАВЛЕННЫЙ ИМПОРТ

# --- ИСПРАВЛЕННЫЕ ИМПОРТЫ ---
from app.admin.views.user import UserAdmin
from app.api.endpoints.support import reply_to_ticket
from app.db.models import User, SupportTicket, BannedIP
from app.core.enums import PlanName, TicketStatus
from app.core.config import settings
from app.services.system_service import SystemService
from app.core.plans import get_limits_for_plan, is_feature_available_for_plan

ASYNC_TEST = pytest.mark.asyncio

class TestAdminSuperpowers:
    @ASYNC_TEST
    async def test_admin_has_access_to_disabled_feature(self, test_user, admin_user, mocker):
        mocker.patch.object(SystemService, 'is_feature_enabled', return_value=False)
        
        # Проверяем обычного пользователя - доступа нет
        assert not is_feature_available_for_plan(test_user.plan, "any_feature", user=test_user)
        
        # Проверяем админа - доступ есть всегда, даже если фича выключена глобально
        assert is_feature_available_for_plan(admin_user.plan, "any_feature", user=admin_user)

    @ASYNC_TEST
    async def test_impersonate_action_creates_correct_token(self, db_session, admin_user, test_user):
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        response = await admin_view.impersonate(mock_request, pks=[test_user.id])
        
        assert response.status_code == 200
        body = response.body.decode()
        data = eval(body)
        
        assert data['status'] == 'success'
        access_token = data['access_token']
        
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        assert payload['sub'] == str(admin_user.id)
        assert payload['profile_id'] == str(test_user.id)
        assert payload['scope'] == 'impersonate'

class TestTicketSystemLimits:
    @ASYNC_TEST
    async def test_user_cannot_reopen_ticket_more_than_limit(self, db_session, test_user, mocker):
        mocker.patch.object(SystemService, 'get_ticket_reopen_limit', return_value=1)
        
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.RESOLVED, reopen_count=1)
        db_session.add(ticket)
        await db_session.commit()
        
        with pytest.raises(HTTPException) as excinfo:
            # Создаем мок для тела запроса
            mock_message_data = MagicMock(message="one more time")
            await reply_to_ticket(ticket_id=ticket.id, message_data=mock_message_data, current_user=test_user, db=db_session)
        
        assert excinfo.value.status_code == 403
        assert "лимит" in excinfo.value.detail.lower()

    @ASYNC_TEST
    async def test_user_can_reopen_ticket_within_limit(self, db_session, test_user, mocker):
        mocker.patch.object(SystemService, 'get_ticket_reopen_limit', return_value=2)
        
        ticket = SupportTicket(user_id=test_user.id, subject="Test", status=TicketStatus.RESOLVED, reopen_count=1)
        db_session.add(ticket)
        await db_session.commit()

        mock_message_data = MagicMock(message="I can do this")
        await reply_to_ticket(ticket_id=ticket.id, message_data=mock_message_data, current_user=test_user, db=db_session)

        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.OPEN
        assert ticket.reopen_count == 2
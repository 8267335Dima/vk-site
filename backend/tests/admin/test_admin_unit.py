import json
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone

from app.admin.views.management.automation import AutomationAdmin
from app.admin.views.monitoring.action_log import ActionLogAdmin
from app.admin.views.monitoring.daily_stats import DailyStatsAdmin
from app.admin.views.management.user import UserAdmin
from app.db.models import User, Plan
from app.core.enums import PlanName, AutomationType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ASYNC_TEST = pytest.mark.asyncio


class TestAdminFormatters:
    def test_automation_formatters(self):
        user_formatter = AutomationAdmin.column_formatters["user"]
        assert user_formatter(MagicMock(user=MagicMock(vk_id=123)), None) == "User 123"
        assert user_formatter(MagicMock(user=None), None) == "Unknown"
        
        type_formatter = AutomationAdmin.column_formatters[AutomationAdmin.model.automation_type]
        assert type_formatter(MagicMock(automation_type=AutomationType.LIKE_FEED), None) == "like_feed"
        assert type_formatter(MagicMock(automation_type="CUSTOM"), None) == "CUSTOM"
        assert type_formatter(MagicMock(automation_type=None), None) == "Не указан"
        
        active_formatter = AutomationAdmin.column_formatters[AutomationAdmin.model.is_active]
        assert active_formatter(MagicMock(is_active=True), None) == "✅"
        assert active_formatter(MagicMock(is_active=False), None) == "❌"

    def test_action_log_user_formatter(self):
        formatter = ActionLogAdmin.column_formatters["user"]
        assert formatter(MagicMock(user=MagicMock(vk_id=543)), None) == "User 543"
        assert formatter(MagicMock(user=None), None) == "Unknown"

    def test_daily_stats_user_id_formatter(self):
        formatter = DailyStatsAdmin.column_formatters[DailyStatsAdmin.model.user_id]
        assert formatter(MagicMock(user_id=999), None) == "User 999"

    def test_user_plan_expires_at_formatter(self):
        formatter = UserAdmin.column_formatters[User.plan_expires_at]
        assert formatter(MagicMock(plan_expires_at=datetime(2025, 10, 20, 15, 30)), None) == "2025-10-20 15:30"
        assert formatter(MagicMock(plan_expires_at=None), None) == "Не истекает"


class TestUserAdminActions:

    @ASYNC_TEST
    async def test_extend_subscription_for_expired_user(self, db_session: AsyncSession):
        expired_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.EXPIRED.name))).scalar_one()
        plus_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PLUS.name))).scalar_one()

        test_user = User(vk_id=98765, encrypted_vk_token="token", plan_id=expired_plan.id, plan_expires_at=datetime.now(timezone.utc) - timedelta(days=10))
        db_session.add(test_user)
        await db_session.commit()
        await db_session.refresh(test_user, ["plan"])

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        await admin_view.extend_subscription.__wrapped__(admin_view, mock_request, pks=[test_user.id])

        await db_session.refresh(test_user)
        assert test_user.plan_expires_at > datetime.now(timezone.utc) + timedelta(days=29)
        assert test_user.plan_id == plus_plan.id

    @ASYNC_TEST
    async def test_extend_subscription_with_empty_pks_list(self):
        mock_session = AsyncMock()
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = UserAdmin()

        response = await admin_view.extend_subscription.__wrapped__(admin_view, mock_request, pks=[])

        mock_session.get.assert_not_called()
        mock_session.commit.assert_not_awaited() 
        
        # Исправленная строка:
        response_data = json.loads(response.body)
        assert response_data["message"] == "Подписка продлена для 0 пользователей."
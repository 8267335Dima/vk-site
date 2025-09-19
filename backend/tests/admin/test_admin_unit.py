# tests/admin/test_admin_unit.py

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone

# Обновленные импорты:
from app.admin.views.management.automation import AutomationAdmin
from app.admin.views.monitoring.action_log import ActionLogAdmin
from app.admin.views.monitoring.daily_stats import DailyStatsAdmin
from app.admin.views.support.ticket import SupportTicketAdmin
from app.admin.views.management.user import UserAdmin

from app.db.models import User
from app.core.enums import PlanName, AutomationType

ASYNC_TEST = pytest.mark.asyncio


class TestAdminFormatters:
    """Тестируем ВСЕ кастомные форматтеры для колонок."""

    def test_automation_formatters(self):
        # User Formatter
        user_formatter = AutomationAdmin.column_formatters["user"]
        assert user_formatter(MagicMock(user=MagicMock(vk_id=123)), None) == "User 123"
        assert user_formatter(MagicMock(user=None), None) == "Unknown"
        
        # Type Formatter
        type_formatter = AutomationAdmin.column_formatters[AutomationAdmin.model.automation_type]
        assert type_formatter(MagicMock(automation_type=AutomationType.LIKE_FEED), None) == "like_feed"
        assert type_formatter(MagicMock(automation_type="CUSTOM"), None) == "CUSTOM"
        assert type_formatter(MagicMock(automation_type=None), None) == "Не указан"
        
        # Active Formatter
        active_formatter = AutomationAdmin.column_formatters[AutomationAdmin.model.is_active]
        assert active_formatter(MagicMock(is_active=True), None) == "Active"
        assert active_formatter(MagicMock(is_active=False), None) == "Inactive"

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
    """Тестируем кастомные действия в UserAdmin."""

    @ASYNC_TEST
    async def test_extend_subscription_for_expired_user(self, mocker):
        mocker.patch("app.admin.auth.AdminAuth.authenticate", return_value=True)
        mock_session = AsyncMock()
        mock_user = MagicMock(spec=User, plan=PlanName.EXPIRED.name, plan_expires_at=None)
        mock_session.get.return_value = mock_user
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = UserAdmin()
        mocker.patch('app.admin.views.user.get_limits_for_plan', return_value={'daily_likes_limit': 100})

        await admin_view.extend_subscription(mock_request, pks=[1])

        assert mock_user.plan_expires_at > datetime.now(timezone.utc) + timedelta(days=29)
        assert mock_user.plan == PlanName.PLUS.name
        assert mock_user.daily_likes_limit == 100
        mock_session.commit.assert_awaited_once()

    @ASYNC_TEST
    async def test_extend_subscription_with_empty_pks_list(self, mocker):
        mocker.patch("app.admin.auth.AdminAuth.authenticate", return_value=True)
        mock_session = AsyncMock()
        mock_request = MagicMock(state=MagicMock(session=mock_session))
        admin_view = UserAdmin()

        response = await admin_view.extend_subscription(mock_request, pks=[])

        mock_session.get.assert_not_called()
        mock_session.commit.assert_awaited_once()
        assert response["message"] == "Подписка продлена для 0 пользователей."
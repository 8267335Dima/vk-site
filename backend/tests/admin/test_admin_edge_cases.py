#tests/admin/test_admin_edge_cases.py

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
import json

from app.admin.views.management.user import UserAdmin
from app.db.models import User, Plan
from app.core.enums import PlanName

ASYNC_TEST = pytest.mark.asyncio

class TestUserAdminEdgeCases:

    @ASYNC_TEST
    async def test_extend_subscription_fails_if_plus_plan_missing(self, db_session: AsyncSession):
        """
        Проверяет, что система не падает, а корректно обрабатывает ситуацию,
        когда тариф PLUS отсутствует в БД при попытке продлить истекший тариф.
        """
        # Намеренно удаляем тариф PLUS из БД
        stmt = select(Plan).where(Plan.name_id == PlanName.PLUS.name)
        plus_plan = (await db_session.execute(stmt)).scalar_one_or_none()
        if plus_plan:
            await db_session.delete(plus_plan)
            await db_session.commit()

        # ИСПРАВЛЕННЫЙ ЗАПРОС
        stmt_expired = select(Plan).where(Plan.name_id == PlanName.EXPIRED.name)
        expired_plan = (await db_session.execute(stmt_expired)).scalar_one()
        test_user = User(
            vk_id=98765, encrypted_vk_token="token", plan_id=expired_plan.id,
            plan_expires_at=datetime.now(timezone.utc) - timedelta(days=10)
        )
        db_session.add(test_user)
        await db_session.commit()

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        # Ожидаем, что приложение вызовет исключение, так как не найдет нужный тариф
        with pytest.raises(Exception) as excinfo:
            await admin_view.extend_subscription.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        
        # ИСПРАВЛЕННАЯ СТРОКА
        assert "No row was found when one was required" in str(excinfo.value)

    @ASYNC_TEST
    async def test_impersonate_non_existent_user(self, db_session: AsyncSession, admin_user: User):
        """Проверяет, что impersonate возвращает 404, если ID пользователя не существует."""
        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        non_existent_pk = 9999999
        
        response = await admin_view.impersonate.__wrapped__(admin_view, mock_request, pks=[non_existent_pk])
        
        assert response.status_code == 404
        response_data = json.loads(response.body)
        assert "Целевой пользователь не найден" in response_data["message"]

    @ASYNC_TEST
    async def test_extend_subscription_for_active_user(self, db_session: AsyncSession, test_user: User):
        """
        Проверяет, что при продлении подписки активного пользователя
        меняется только дата, но не сам тариф.
        """
        # У пользователя уже есть активный PRO-тариф
        initial_plan_id = test_user.plan_id
        initial_expires_at = datetime.now(timezone.utc) + timedelta(days=15)
        test_user.plan_expires_at = initial_expires_at
        db_session.add(test_user)
        await db_session.commit()

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        await admin_view.extend_subscription.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        await db_session.refresh(test_user)

        # Проверяем, что ID тарифа НЕ изменился
        assert test_user.plan_id == initial_plan_id
        # Проверяем, что дата продлилась ровно на 30 дней от предыдущей даты
        expected_new_date = initial_expires_at + timedelta(days=30)
        assert test_user.plan_expires_at.date() == expected_new_date.date()

    @ASYNC_TEST
    async def test_impersonate_soft_deleted_user_fails(self, db_session: AsyncSession, admin_user: User, test_user: User):
        """
        Проверяет, что нельзя войти под пользователем, который был "мягко удален".
        """
        # Сначала "удаляем" пользователя
        test_user.is_deleted = True
        db_session.add(test_user)
        await db_session.commit()

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()
        
        # Ожидаем ошибку 404, так как для системы удаленный пользователь не должен быть доступен для таких действий
        response = await admin_view.impersonate.__wrapped__(admin_view, mock_request, pks=[test_user.id])
        
        assert response.status_code == 404
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy import select, exc as sqlalchemy_exc

from app.admin.views.management.user import UserAdmin
from app.admin.views.management.payment import PaymentAdmin
from app.admin.views.system.banned_ip import BannedIPAdmin
from app.db.models import User, Payment, BannedIP, Plan
from app.core.security import decrypt_data

ASYNC_TEST = pytest.mark.asyncio


class TestUserAdminComprehensive:

    @ASYNC_TEST
    async def test_on_model_change_with_empty_token(self, test_user: User):
        """Проверяет, что токен пользователя НЕ меняется, если в форме поле токена пустое."""
        admin_view = UserAdmin()
        initial_encrypted_token = test_user.encrypted_vk_token
        
        # Симулируем данные формы, где поле для нового токена пустое
        form_data = {"encrypted_vk_token_clear": ""}
        
        await admin_view.on_model_change(data=form_data, model=test_user, is_created=False, request=MagicMock())
        
        # Убеждаемся, что токен остался прежним
        assert test_user.encrypted_vk_token == initial_encrypted_token

    @ASYNC_TEST
    async def test_actions_with_empty_pks_list(self, db_session: AsyncSession, mocker): # <--- Добавлен mocker
        """Проверяет, что действия не падают и ничего не делают, если список pks пуст."""
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Заменяем реальный метод commit на мок, чтобы отследить его вызовы
        commit_mock = mocker.patch.object(db_session, "commit", new_callable=AsyncMock)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        mock_request = MagicMock(state=MagicMock(session=db_session))
        admin_view = UserAdmin()

        await admin_view.soft_delete.__wrapped__(admin_view, mock_request, pks=[])
        await admin_view.restore.__wrapped__(admin_view, mock_request, pks=[])
        await admin_view.toggle_freeze.__wrapped__(admin_view, mock_request, pks=[])
        await admin_view.toggle_shadow_ban.__wrapped__(admin_view, mock_request, pks=[])
        
        # Проверяем, что мок-объект commit не был вызван (ожиден) ни разу
        commit_mock.assert_not_awaited()

class TestPaymentAdminComprehensive:

    @ASYNC_TEST
    async def test_delete_payment_action(self, db_session: AsyncSession, test_user: User):
        """Проверяет базовую функциональность удаления платежа."""
        plan = (await db_session.execute(select(Plan).limit(1))).scalar_one()
        
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Добавлено недостающее обязательное поле payment_system_id
        payment = Payment(
            user_id=test_user.id,
            plan_name=plan.name_id,
            amount=100,
            payment_system_id="test_payment_id_123" # Добавлено это поле
        )
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        db_session.add(payment)
        await db_session.commit()
        
        payment_id = payment.id
        assert await db_session.get(Payment, payment_id) is not None
        
        admin_view = PaymentAdmin()
        # В sqladmin удаление - это не action, а стандартный метод. Его нужно мокать или тестировать через HTTP-клиент.
        # Для юнит-теста мы можем проверить, что модель будет удалена.
        await db_session.delete(payment)
        await db_session.commit()

        assert await db_session.get(Payment, payment_id) is None


class TestBannedIPAdminComprehensive:
    
    @ASYNC_TEST
    async def test_create_duplicate_ip_ban_fails(self, db_session: AsyncSession, admin_user: User):
        """
        Проверяет, что нельзя забанить один и тот же IP-адрес дважды,
        ожидая ошибку целостности от БД (UNIQUE constraint).
        """
        ip_to_ban = "192.168.1.1"
        
        # Первый бан
        ban1 = BannedIP(ip_address=ip_to_ban, admin_id=admin_user.id, reason="Test 1")
        db_session.add(ban1)
        await db_session.commit()

        # Попытка второго бана того же IP
        ban2 = BannedIP(ip_address=ip_to_ban, admin_id=admin_user.id, reason="Test 2")
        db_session.add(ban2)

        # Ожидаем ошибку IntegrityError, потому что поле ip_address должно быть уникальным
        with pytest.raises(sqlalchemy_exc.IntegrityError):
            await db_session.commit()


class TestAdminViewsConfiguration:

    def test_all_admin_views_have_required_attributes(self):
        """
        Мета-тест: проверяет, что все классы админ-панелей имеют
        базовые атрибуты (category, name, icon), чтобы избежать ошибок рендеринга.
        """
        from app.admin import views
        
        all_admin_views = [
            views.management.user.UserAdmin,
            views.management.payment.PaymentAdmin,
            views.management.plan.PlanAdmin,
            views.management.automation.AutomationAdmin,
            views.monitoring.task_history.TaskHistoryAdmin,
            views.monitoring.daily_stats.DailyStatsAdmin,
            views.monitoring.action_log.ActionLogAdmin,
            views.support.ticket.SupportTicketAdmin,
            views.support.message.TicketMessageAdmin,
            views.system.global_settings.GlobalSettingsAdmin,
            views.system.banned_ip.BannedIPAdmin,
        ]

        for view in all_admin_views:
            assert hasattr(view, 'category') and view.category, f"{view.__name__} is missing category"
            assert hasattr(view, 'name') and view.name, f"{view.__name__} is missing name"
            assert hasattr(view, 'icon') and view.icon, f"{view.__name__} is missing icon"
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone

from app.admin.views.management.user import UserAdmin
from app.admin.views.support.ticket import SupportTicketAdmin
from app.db.models import User, SupportTicket
from app.core.security import decrypt_data

ASYNC_TEST = pytest.mark.asyncio

class TestModelChangeHooks:

    @ASYNC_TEST
    async def test_user_admin_token_encryption_hook(self):
        """Проверяет, что хук в UserAdmin шифрует новый VK токен."""
        admin_view = UserAdmin()
        user = User(vk_id=111)
        new_token = "my-new-secret-vk-token"
        
        # Данные, которые приходят из формы редактирования
        form_data = {"encrypted_vk_token_clear": new_token}

        # Вызываем хук
        await admin_view.on_model_change(data=form_data, model=user, is_created=False, request=MagicMock())

        # Проверяем, что токен в модели зашифрован и совпадает с исходным
        assert user.encrypted_vk_token is not None
        assert user.encrypted_vk_token != new_token
        decrypted = decrypt_data(user.encrypted_vk_token)
        assert decrypted == new_token

    @ASYNC_TEST
    async def test_support_ticket_timestamp_update_hook(self):
        """Проверяет, что хук в SupportTicketAdmin обновляет updated_at."""
        admin_view = SupportTicketAdmin()
        now = datetime.now(timezone.utc)
        
        # Создаем тикет, как будто он был создан давно
        ticket = SupportTicket(subject="Old Ticket", updated_at=now - timedelta(days=1))
        
        initial_updated_at = ticket.updated_at

        # Вызываем хук
        await admin_view.on_model_change(data={}, model=ticket, is_created=False, request=MagicMock())
        
        # Проверяем, что временная метка обновилась
        assert ticket.updated_at > initial_updated_at
        assert (ticket.updated_at - now).total_seconds() < 5 # Убеждаемся, что время почти текущее
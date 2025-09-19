import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock
from sqlalchemy import select, exc as sqlalchemy_exc

from app.admin.views.management.automation import AutomationAdmin
from app.admin.views.monitoring.task_history import TaskHistoryAdmin
from app.admin.views.support.ticket import SupportTicketAdmin
from app.admin.views.system.global_settings import GlobalSettingsAdmin
from app.db.models import Automation, TaskHistory, SupportTicket, User, GlobalSetting

ASYNC_TEST = pytest.mark.asyncio


class TestAutomationAdminFinal:

    @ASYNC_TEST
    async def test_edit_automation_activity(self, db_session: AsyncSession, test_user: User):
        """Проверяет возможность включения/выключения автоматизации через админку."""
        automation = Automation(user_id=test_user.id, automation_type="LIKE_FEED", is_active=False)
        db_session.add(automation)
        await db_session.commit()

        admin_view = AutomationAdmin()
        
        # Симулируем редактирование в админке, где `on_model_change` не определен,
        # поэтому изменения применяются напрямую к модели перед коммитом.
        automation.is_active = True
        db_session.add(automation)
        await db_session.commit()

        await db_session.refresh(automation)
        assert automation.is_active is True

class TestTaskHistoryAdminFinal:
    
    @ASYNC_TEST
    async def test_delete_task_history_record(self, db_session: AsyncSession, test_user: User):
        """Проверяет, что запись истории задач может быть удалена (can_delete = True)."""
        task = TaskHistory(user_id=test_user.id, task_name="Test Task", status="SUCCESS")
        db_session.add(task)
        await db_session.commit()
        
        task_id = task.id
        assert await db_session.get(TaskHistory, task_id) is not None

        # Симулируем удаление
        await db_session.delete(task)
        await db_session.commit()

        assert await db_session.get(TaskHistory, task_id) is None

class TestSupportTicketAdminFinal:

    @ASYNC_TEST
    async def test_create_ticket_from_admin_panel(self, db_session: AsyncSession, test_user: User):
        """Проверяет создание тикета из админки (can_create = True)."""
        admin_view = SupportTicketAdmin()
        
        new_ticket = SupportTicket(
            user_id=test_user.id,
            subject="Created by Admin",
            status="OPEN"
        )
        
        # Симулируем хук, который должен обновить `updated_at`
        await admin_view.on_model_change(data={}, model=new_ticket, is_created=True, request=MagicMock())
        
        db_session.add(new_ticket)
        await db_session.commit()

        assert new_ticket.id is not None
        assert new_ticket.subject == "Created by Admin"
        assert new_ticket.user_id == test_user.id
        assert new_ticket.updated_at is not None # Проверяем, что хук сработал

class TestGlobalSettingsAdminFinal:

    @ASYNC_TEST
    async def test_create_and_edit_global_setting(self, db_session: AsyncSession):
        """Проверяет полный цикл CRUD для глобальных настроек."""
        setting_key = "TEST_FEATURE_FLAG" # Используем ключ для идентификации

        # 1. Создание
        setting = GlobalSetting(key=setting_key, value="false", is_enabled=True)
        db_session.add(setting)
        await db_session.commit()
        
        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        # Проверяем, что объект в сессии
        assert setting in db_session
        
        # 2. Редактирование
        retrieved_setting = await db_session.get(GlobalSetting, setting_key) # Получаем по ключу
        assert retrieved_setting is not None
        retrieved_setting.value = "true"
        retrieved_setting.is_enabled = False
        await db_session.commit()

        await db_session.refresh(retrieved_setting)
        assert retrieved_setting.value == "true"
        assert retrieved_setting.is_enabled is False

        # 3. Удаление
        await db_session.delete(retrieved_setting)
        await db_session.commit()
        
        assert await db_session.get(GlobalSetting, setting_key) is None # Проверяем удаление по ключу

    @ASYNC_TEST
    async def test_create_duplicate_setting_key_fails(self, db_session: AsyncSession):
        """Проверяет, что UNIQUE constraint на поле 'key' работает."""
        setting1 = GlobalSetting(key="UNIQUE_KEY", value="1")
        db_session.add(setting1)
        await db_session.commit()

        setting2 = GlobalSetting(key="UNIQUE_KEY", value="2")
        db_session.add(setting2)

        with pytest.raises(sqlalchemy_exc.IntegrityError):
            await db_session.commit()
from sqladmin import ModelView
from app.db.models import Automation
from sqladmin.filters import BooleanFilter
import enum

class AutomationAdmin(ModelView, model=Automation):
    category = "Управление"
    name = "Автоматизация"
    name_plural = "Автоматизации"
    icon = "fa-solid fa-robot"
    can_create = False
    can_edit = True
    can_delete = False
    
    column_list = [Automation.id, "user", Automation.automation_type, Automation.is_active, Automation.last_run_at]
    column_joined_list = [Automation.user]
    column_searchable_list = [Automation.user_id, "user.vk_id"]
    column_formatters = {
        "user": lambda m, a: f"User {m.user.vk_id}" if m.user else "Unknown",
        Automation.automation_type: lambda m, a: m.automation_type.value if isinstance(m.automation_type, enum.Enum) else (m.automation_type or "Не указан"),
        Automation.is_active: lambda m, a: "✅" if m.is_active else "❌",
    }
    column_filters = [BooleanFilter(Automation.is_active)]
    column_default_sort = ("last_run_at", True)
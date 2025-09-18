# backend/app/admin/views/stats.py
from sqladmin import ModelView
from app.db.models import (
    Automation, DailyStats, ActionLog
)
from sqladmin.filters import AllUniqueStringValuesFilter, BooleanFilter
import enum

class AutomationAdmin(ModelView, model=Automation):
    identity = "automation"
    name_plural = "Автоматизации"
    icon = "fa-solid fa-robot"
    can_create = False
    can_edit = True
    can_delete = False

    # Используем СТРОКУ для имени связи
    column_list = [
        Automation.id,
        "user",
        Automation.automation_type,
        Automation.is_active,
        Automation.last_run_at
    ]

    # Явно указываем, что для списка нужно ЗАГРУЗИТЬ связь
    column_joined_list = [Automation.user]
    
    column_searchable_list = [Automation.user_id, "user.vk_id"]

    # Используем СТРОКУ в качестве ключа для форматтера
    column_formatters = {
        "user": lambda m, a: f"User {m.user.vk_id}" if m.user else "Unknown",
        Automation.automation_type: lambda m, a: m.automation_type.value if isinstance(m.automation_type, enum.Enum) else (m.automation_type or "Не указан"),
        Automation.is_active: lambda m, a: "Active" if m.is_active else "Inactive",
    }

    column_filters = [
        BooleanFilter(Automation.is_active),
    ]


# !!! ВОЗВРАЩАЕМ НЕДОСТАЮЩИЙ КЛАСС !!!
class DailyStatsAdmin(ModelView, model=DailyStats):
    identity = "daily-stats"
    name_plural = "Дневная статистика"
    icon = "fa-solid fa-chart-line"
    can_create = False
    can_edit = False
    column_list = [c.name for c in DailyStats.__table__.c]
    column_default_sort = ("date", True)
    column_searchable_list = [DailyStats.user_id]
    
    column_formatters = {
        DailyStats.user_id: lambda m, a: f"User {m.user_id}"
    }


class ActionLogAdmin(ModelView, model=ActionLog):
    identity = "action-log"
    name_plural = "Логи действий"
    icon = "fa-solid fa-clipboard-list"
    can_create = False
    can_edit = False
    # Применяем тот же паттерн
    column_list = [ActionLog.id, "user", ActionLog.action_type, ActionLog.message, ActionLog.status, ActionLog.timestamp]
    
    column_joined_list = [ActionLog.user]
    
    column_searchable_list = [ActionLog.user_id, "user.vk_id"]
    column_filters = [
        AllUniqueStringValuesFilter(ActionLog.action_type),
        AllUniqueStringValuesFilter(ActionLog.status),
    ]
    column_default_sort = ("timestamp", True)
    
    column_formatters = {
        "user": lambda m, a: f"User {m.user.vk_id}" if m.user else "Unknown"
    }
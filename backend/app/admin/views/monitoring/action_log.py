from sqladmin import ModelView
from app.db.models import ActionLog
from sqladmin.filters import AllUniqueStringValuesFilter

class ActionLogAdmin(ModelView, model=ActionLog):
    category = "Мониторинг"
    name = "Лог Действий"
    name_plural = "Логи Действий"
    icon = "fa-solid fa-clipboard-list"
    can_create = False
    can_edit = False
    can_delete = False
    
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
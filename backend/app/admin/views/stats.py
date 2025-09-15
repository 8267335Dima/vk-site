from sqladmin import ModelView
from app.db.models import Automation, DailyStats, ActionLog

class AutomationAdmin(ModelView, model=Automation):
    name_plural = "Автоматизации"
    icon = "fa-solid fa-robot"
    column_list = [Automation.user, Automation.automation_type, Automation.is_active, Automation.last_run_at]
    column_searchable_list = [Automation.user_id, "user.vk_id"]
    column_filters = [Automation.automation_type, Automation.is_active]

class DailyStatsAdmin(ModelView, model=DailyStats):
    name_plural = "Дневная статистика"
    icon = "fa-solid fa-chart-line"
    can_create = False
    can_edit = False
    column_list = [c.name for c in DailyStats.__table__.c]
    column_default_sort = ("date", True)
    column_searchable_list = [DailyStats.user_id]

class ActionLogAdmin(ModelView, model=ActionLog):
    name_plural = "Логи действий"
    icon = "fa-solid fa-clipboard-list"
    can_create = False
    can_edit = False
    column_list = [ActionLog.id, ActionLog.user, ActionLog.action_type, ActionLog.message, ActionLog.status, ActionLog.timestamp]
    column_searchable_list = [ActionLog.user_id, "user.vk_id"]
    column_filters = [ActionLog.action_type, ActionLog.status]
    column_default_sort = ("timestamp", True)
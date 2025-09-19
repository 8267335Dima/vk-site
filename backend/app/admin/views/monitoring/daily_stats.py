from sqladmin import ModelView
from app.db.models import DailyStats

class DailyStatsAdmin(ModelView, model=DailyStats):
    category = "Мониторинг"
    name = "Дневная Статистика"
    name_plural = "Дневная Статистика"
    icon = "fa-solid fa-chart-line"
    can_create = False
    can_edit = False
    can_delete = False
    
    column_list = [c.name for c in DailyStats.__table__.c]
    column_default_sort = ("date", True)
    column_searchable_list = [DailyStats.user_id]

    column_formatters = {
        DailyStats.user_id: lambda m, a: f"User {m.user_id}"
    }
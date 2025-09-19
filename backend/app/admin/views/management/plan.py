from sqladmin import ModelView
from app.db.models import Plan

class PlanAdmin(ModelView, model=Plan):
    category = "Управление"
    name = "Тариф"
    name_plural = "Тарифы"
    icon = "fa-solid fa-star"
    
    can_create = True
    can_edit = True
    can_delete = False

    column_list = [Plan.id, Plan.name_id, Plan.display_name, Plan.base_price, Plan.is_active, Plan.is_popular]
    column_searchable_list = [Plan.name_id, Plan.display_name]
    column_filters = [Plan.is_active]
    column_default_sort = ("base_price", False)

    form_columns = [
        Plan.name_id,
        Plan.display_name,
        Plan.description,
        Plan.base_price,
        Plan.limits,
        Plan.available_features,
        Plan.is_active,
        Plan.is_popular,
    ]

    column_labels = {
        "name_id": "Системное имя (ID)",
        "display_name": "Отображаемое имя",
        "base_price": "Цена (RUB)",
        "is_active": "Активен для покупки",
        "is_popular": "Популярный",
        "limits": "Лимиты (JSON)",
        "available_features": "Доступные функции (JSON)"
    }
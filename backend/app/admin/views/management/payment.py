from sqladmin import ModelView
from app.db.models import Payment, PaymentStatus
from sqladmin.filters import AllUniqueStringValuesFilter

class PaymentAdmin(ModelView, model=Payment):
    category = "Управление"
    name = "Платеж"
    name_plural = "Платежи"
    icon = "fa-solid fa-ruble-sign"
    can_create = False
    can_edit = False
    can_delete = True
    
    column_list = [Payment.id, Payment.user, Payment.plan_name, Payment.amount, Payment.status, Payment.created_at]
    column_searchable_list = [Payment.user_id, "user.vk_id"]
    
    column_filters = [
        AllUniqueStringValuesFilter(Payment.status),
        AllUniqueStringValuesFilter(Payment.plan_name),
    ]
    
    column_default_sort = ("created_at", True)
    column_labels = {
        "plan_name": "Название тарифа"
    }
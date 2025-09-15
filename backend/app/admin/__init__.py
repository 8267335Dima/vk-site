from sqladmin import Admin
from .auth import authentication_backend

# Импортируем все наши представления из модулей
from .views.user import UserAdmin
from .views.support import SupportTicketAdmin
from .views.payment import PaymentAdmin
from .views.stats import AutomationAdmin, DailyStatsAdmin, ActionLogAdmin

def init_admin(app, engine):
    admin = Admin(app, engine, authentication_backend=authentication_backend, title="SMM Combine Admin")
    
    # Регистрируем импортированные представления
    admin.add_view(UserAdmin)
    admin.add_view(SupportTicketAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(AutomationAdmin)
    admin.add_view(DailyStatsAdmin)
    admin.add_view(ActionLogAdmin)
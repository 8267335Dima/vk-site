# backend/app/admin/__init__.py

from sqladmin import Admin
from app.core.config import settings
from .auth import AdminAuth

def init_admin(app, engine):
    from .views.management.user import UserAdmin
    from .views.management.payment import PaymentAdmin
    from .views.management.plan import PlanAdmin
    from .views.management.automation import AutomationAdmin
    
    from .views.monitoring.task_history import TaskHistoryAdmin
    from .views.monitoring.daily_stats import DailyStatsAdmin
    from .views.monitoring.action_log import ActionLogAdmin

    from .views.support.ticket import SupportTicketAdmin
    from .views.support.message import TicketMessageAdmin

    from .views.system.global_settings import GlobalSettingsAdmin
    from .views.system.banned_ip import BannedIPAdmin
    from .views.system.admin_actions import AdminActionsView
    
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    
    admin = Admin(app, engine, authentication_backend=authentication_backend, title="SMM Combine Admin")


    admin.add_view(UserAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(PlanAdmin)
    admin.add_view(AutomationAdmin)

    admin.add_view(TaskHistoryAdmin)
    admin.add_view(DailyStatsAdmin)
    admin.add_view(ActionLogAdmin)

    admin.add_view(SupportTicketAdmin)
    admin.add_view(TicketMessageAdmin)

    admin.add_view(GlobalSettingsAdmin)
    admin.add_view(BannedIPAdmin)
    admin.add_view(AdminActionsView)

    app.state.admin = admin
# backend/app/admin/__init__.py

from sqladmin import Admin
from app.core.config import settings
from .auth import AdminAuth

def init_admin(app, engine):
    from .views.user import UserAdmin
    from .views.support import SupportTicketAdmin
    from .views.payment import PaymentAdmin
    from .views.stats import AutomationAdmin, DailyStatsAdmin, ActionLogAdmin
    from .views.system import GlobalSettingsAdmin, BannedIPAdmin
    
    authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)
    
    admin = Admin(
        app, engine, authentication_backend=authentication_backend, title="SMM Combine Admin",
    )

    admin.add_view(UserAdmin)
    admin.add_view(SupportTicketAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(AutomationAdmin)
    admin.add_view(DailyStatsAdmin)
    admin.add_view(ActionLogAdmin)
    admin.add_view(GlobalSettingsAdmin)
    admin.add_view(BannedIPAdmin)

    app.state.admin = admin
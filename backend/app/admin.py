# backend/app/admin.py
import secrets
from datetime import timedelta
from fastapi import Request, HTTPException, status
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from jose import jwt, JWTError

from app.db.models import User, Payment, Automation, DailyStats, ActionLog
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import AsyncSessionFactory

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        is_user_correct = secrets.compare_digest(username, settings.ADMIN_USER)
        is_password_correct = secrets.compare_digest(password, settings.ADMIN_PASSWORD)

        if is_user_correct and is_password_correct:
            access_token_expires = timedelta(hours=8)
            token_data = {"sub": username, "scope": "admin_access"}
            access_token = create_access_token(data=token_data, expires_delta=access_token_expires)
            request.session.update({"token": access_token})
            return True

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        if settings.ADMIN_IP_WHITELIST:
            allowed_ips = [ip.strip() for ip in settings.ADMIN_IP_WHITELIST.split(',')]
            if request.client and request.client.host not in allowed_ips:
                return False

        token = request.session.get("token")
        if not token:
            return False

        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            if payload.get("scope") != "admin_access":
                return False
            
            async with AsyncSessionFactory() as session:
                admin_user = await session.get(User, int(settings.ADMIN_VK_ID))
                if not admin_user or not admin_user.is_admin:
                    return False

        except JWTError:
            return False

        return True

authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.vk_id, User.plan, User.plan_expires_at, User.is_admin, User.created_at]
    form_columns = [User.plan, User.plan_expires_at, User.is_admin, User.daily_likes_limit, User.daily_add_friends_limit]
    column_searchable_list = [User.vk_id]
    column_default_sort = ("created_at", True)
    name_plural = "Пользователи"

class PaymentAdmin(ModelView, model=Payment):
    column_list = [Payment.id, Payment.user_id, Payment.plan_name, Payment.amount, Payment.status, Payment.created_at]
    column_searchable_list = [Payment.user_id]
    column_default_sort = ("created_at", True)
    name_plural = "Платежи"

class AutomationAdmin(ModelView, model=Automation):
    column_list = [Automation.user_id, Automation.automation_type, Automation.is_active, Automation.last_run_at]
    column_searchable_list = [Automation.user_id]
    name_plural = "Автоматизации"

class DailyStatsAdmin(ModelView, model=DailyStats):
    column_list = [c.name for c in DailyStats.__table__.c]
    column_default_sort = ("date", True)
    name_plural = "Дневная статистика"

class ActionLogAdmin(ModelView, model=ActionLog):
    column_list = [ActionLog.user_id, ActionLog.action_type, ActionLog.message, ActionLog.status, ActionLog.timestamp]
    column_searchable_list = [ActionLog.user_id]
    column_default_sort = ("timestamp", True)
    name_plural = "Логи действий"


def init_admin(app, engine):
    admin = Admin(app, engine, authentication_backend=authentication_backend)
    admin.add_view(UserAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(AutomationAdmin)
    admin.add_view(DailyStatsAdmin)
    admin.add_view(ActionLogAdmin)

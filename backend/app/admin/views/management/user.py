from sqladmin import ModelView, action
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from sqlalchemy.orm import selectinload
from markupsafe import Markup

from app.core.config import settings
from app.db.models import User, LoginHistory, BannedIP, DailyStats, Automation
from sqladmin.filters import BooleanFilter
from app.core.enums import PlanName
from app.core.security import encrypt_data, create_access_token

class UserAdmin(ModelView, model=User):
    category = "Управление"
    name = "Пользователь"
    name_plural = "Пользователи"
    icon = "fa-solid fa-users"
    
    column_list = [User.vk_id, User.plan, User.is_frozen, User.is_shadow_banned, User.is_deleted, User.last_active_at]
    column_details_exclude_list = [User.encrypted_vk_token, User.automations, User.task_history, User.daily_stats, User.action_logs, User.notifications, User.scenarios, User.profile_metrics, User.filter_presets, User.friend_requests, User.heatmap, User.managed_profiles, User.scheduled_posts, User.owned_team, User.team_membership]
    column_searchable_list = [User.vk_id]
    column_filters = [User.plan, User.is_admin, User.is_frozen, User.is_deleted, User.is_shadow_banned]
    column_default_sort = ("created_at", True)

    can_edit = True
    can_create = False
    can_delete = False

    form_columns = [User.plan, User.plan_expires_at, User.is_admin, "encrypted_vk_token_clear", User.is_frozen, User.is_shadow_banned]
    form_overrides = {"encrypted_vk_token_clear": "Password"}
    form_args = {"encrypted_vk_token_clear": {"label": "Новый VK токен (оставить пустым, чтобы не менять)"}}

    column_labels = {
        User.vk_id: "VK ID", User.plan: "Тариф", User.is_frozen: "🧊",
        User.is_shadow_banned: "👻", User.is_deleted: "🗑️",
        User.last_active_at: "Был онлайн", User.login_history: "История входов",
    }

    column_formatters = {
        User.vk_id: lambda m, a: Markup(f'<a href="https://vk.com/id{m.vk_id}" target="_blank">{m.vk_id}</a>'),
        User.is_frozen: lambda m, a: "Да" if m.is_frozen else "Нет",
        User.is_shadow_banned: lambda m, a: "Да" if m.is_shadow_banned else "Нет",
        User.is_deleted: lambda m, a: "Да" if m.is_deleted else "Нет",
        User.last_active_at: lambda m, a: m.last_active_at.strftime('%Y-%m-%d %H:%M') if m.last_active_at else "Никогда"
    }

    async def on_model_change(self, data: dict, model: User, is_created: bool, request: Request):
        if data.get("encrypted_vk_token_clear"):
            model.encrypted_vk_token = encrypt_data(data["encrypted_vk_token_clear"])

    @action(name="impersonate", label="👤 Войти как пользователь", add_in_detail=True, add_in_list=True)
    async def impersonate(self, request: Request, pks: list[int]):
        if len(pks) != 1:
            return JSONResponse({"status": "error", "message": "Выберите одного пользователя."}, status_code=400)
        
        session: AsyncSession = request.state.session
        admin_user_stmt = select(User).where(User.vk_id == int(settings.ADMIN_VK_ID))
        admin = (await session.execute(admin_user_stmt)).scalar_one_or_none()
        if not admin:
             return JSONResponse({"status": "error", "message": "Admin user not found in DB."}, status_code=500)

        target_user_id = int(pks[0])

        token_data = {"sub": str(admin.id), "profile_id": str(target_user_id), "scope": "impersonate"}
        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
        
        script = f"""
            <script>
                const token = '{access_token}';
                alert('Токен для входа от имени пользователя ID {target_user_id} создан. Действует 15 минут.');
                window.history.back();
            </script>
        """
        return HTMLResponse(content=script)
        
    @action(name="soft_delete", label="🗑 Мягко удалить", confirmation_message="Пользователь потеряет доступ, но данные останутся. Уверены?")
    async def soft_delete(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        await session.execute(update(User).where(User.id.in_(pks)).values(is_deleted=True, deleted_at=datetime.now(timezone.utc), is_frozen=True))
        await session.execute(update(Automation).where(Automation.user_id.in_(pks)).values(is_active=False))
        await session.commit()
        return {"message": "Аккаунты помечены как удаленные."}

    @action(name="restore", label="♻️ Восстановить", confirmation_message="Восстановить доступ для пользователя?")
    async def restore(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        await session.execute(update(User).where(User.id.in_(pks)).values(is_deleted=False, deleted_at=None, is_frozen=False))
        await session.commit()
        return {"message": "Аккаунты восстановлены."}

    @action(name="toggle_freeze", label="🧊 Заморозить/Разморозить")
    async def toggle_freeze(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        await session.execute(update(User).where(User.id.in_(pks)).values(is_frozen=text("NOT is_frozen")))
        await session.commit()
        return {"message": "Статус заморозки изменен."}

    @action(name="toggle_shadow_ban", label="👻 Теневой бан вкл/выкл")
    async def toggle_shadow_ban(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        await session.execute(update(User).where(User.id.in_(pks)).values(is_shadow_banned=text("NOT is_shadow_banned")))
        await session.commit()
        return {"message": "Статус теневого бана изменен."}

    @action(name="reset_limits", label="🔄 Сбросить дневные лимиты")
    async def reset_daily_limits(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        today = datetime.now(timezone.utc).date()
        stmt = update(DailyStats).where(DailyStats.user_id.in_(pks), DailyStats.date == today).values(
            likes_count=0, friends_added_count=0, friend_requests_accepted_count=0, stories_viewed_count=0,
            friends_removed_count=0, messages_sent_count=0, posts_created_count=0, groups_joined_count=0, groups_left_count=0
        )
        await session.execute(stmt)
        await session.commit()
        return {"message": "Дневные лимиты сброшены."}
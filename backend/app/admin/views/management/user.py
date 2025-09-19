# backend/app/admin/views/management/user.py

from sqladmin import ModelView, action
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from markupsafe import Markup

from app.core.config import settings
from app.db.models import User, Plan
from app.core.enums import PlanName
from app.core.security import create_access_token, encrypt_data, decrypt_data

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
        User.last_active_at: lambda m, a: m.last_active_at.strftime('%Y-%m-%d %H:%M') if m.last_active_at else "Никогда",
        User.plan_expires_at: lambda m, a: m.plan_expires_at.strftime('%Y-%m-%d %H:%M') if m.plan_expires_at else "Не истекает"
    }

    async def on_model_change(self, data: dict, model: User, is_created: bool, request: Request):
        if model.vk_id == int(settings.ADMIN_VK_ID) and not data.get("is_admin", True):
             raise HTTPException(status_code=400, detail="Нельзя снять права с главного администратора.")
        if data.get("encrypted_vk_token_clear"):
            model.encrypted_vk_token = encrypt_data(data["encrypted_vk_token_clear"])

    @action(name="impersonate", label="👤 Войти как пользователь", add_in_detail=True, add_in_list=True)
    async def impersonate(self, request: Request, pks: list[int]) -> JSONResponse:
        if len(pks) != 1:
            return JSONResponse({"status": "error", "message": "Выберите одного пользователя."}, status_code=400)
        
        session: AsyncSession = request.state.session
        
        admin_user_stmt = select(User).where(User.vk_id == int(settings.ADMIN_VK_ID))
        admin = (await session.execute(admin_user_stmt)).scalar_one_or_none()
        if not admin:
             return JSONResponse({"status": "error", "message": "Admin user not found in DB."}, status_code=500)

        target_user_id = int(pks[0])
        target_user = await session.get(User, target_user_id)
        if not target_user or target_user.is_deleted:
            return JSONResponse({"status": "error", "message": "Целевой пользователь не найден."}, status_code=404)
     
        
        token_data = {"sub": str(admin.id), "profile_id": str(target_user.id), "scope": "impersonate"}
        impersonation_token = create_access_token(data=token_data)
        
        real_vk_token = decrypt_data(target_user.encrypted_vk_token)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"Данные для входа от имени пользователя ID {target_user_id} созданы.",
                "impersonation_token": impersonation_token,
                "real_vk_token": real_vk_token,
            }
        )
    
    @action(name="extend_subscription", label="✅ Продлить подписку (+30 дней)", add_in_list=True, add_in_detail=True)
    async def extend_subscription(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        
        if not pks:
            return JSONResponse(content={"message": "Подписка продлена для 0 пользователей."})

        pks_int = [int(pk) for pk in pks]
        users_result = await session.execute(select(User).where(User.id.in_(pks_int)).options(selectinload(User.plan)))
        users = users_result.scalars().all()

        if not users:
             return JSONResponse(content={"message": "Пользователи не найдены."})

        plus_plan = None
        successful_count = 0
        for user in users:
            now = datetime.now(timezone.utc)
            start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > now else now
            user.plan_expires_at = start_date + timedelta(days=30)

            if user.plan.name_id == PlanName.EXPIRED.name:
                if not plus_plan:
                    plus_plan_result = await session.execute(select(Plan).where(Plan.name_id == PlanName.PLUS.name))
                    plus_plan = plus_plan_result.scalar_one()
                user.plan_id = plus_plan.id
                
                new_limits = plus_plan.limits
                for k, v in new_limits.items():
                    if hasattr(user, k):
                        setattr(user, k, v)
            
            successful_count += 1
        
        await session.commit()

        return JSONResponse(content={"message": f"Подписка продлена для {successful_count} пользователей."})
        
    @action(name="soft_delete", label="🗑 Мягко удалить", confirmation_message="Пользователь потеряет доступ, но данные останутся. Уверены?")
    async def soft_delete(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        
        # --- НОВАЯ ЗАЩИТА ---
        admin_user_stmt = select(User).where(User.vk_id == int(settings.ADMIN_VK_ID))
        admin_id = (await session.execute(admin_user_stmt)).scalar_one().id
        if admin_id in pks_int:
            return JSONResponse(status_code=400, content={"message": "Нельзя удалить главного администратора."})
        # --- КОНЕЦ ЗАЩИТЫ ---

        if pks_int:
            result = await session.execute(select(User).where(User.id.in_(pks_int)))
            for user in result.scalars().all():
                user.is_deleted=True
                user.deleted_at=datetime.now(timezone.utc)
                user.is_frozen=True
            await session.commit()
        return JSONResponse(content={"message": "Аккаунты помечены как удаленные."})

    @action(name="restore", label="♻️ Восстановить", confirmation_message="Восстановить доступ для пользователя?")
    async def restore(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(User).where(User.id.in_(pks_int)))
            for user in result.scalars().all():
                user.is_deleted=False
                user.deleted_at=None
                user.is_frozen=False
            await session.commit()
        return JSONResponse(content={"message": "Аккаунты восстановлены."})

    @action(name="toggle_freeze", label="🧊 Заморозить/Разморозить")
    async def toggle_freeze(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(User).where(User.id.in_(pks_int)))
            for user in result.scalars().all():
                user.is_frozen = not user.is_frozen
            await session.commit()
        return JSONResponse(content={"message": "Статус заморозки изменен."})

    @action(name="toggle_shadow_ban", label="👻 Теневой бан вкл/выкл")
    async def toggle_shadow_ban(self, request: Request, pks: list[int]) -> JSONResponse:
        session: AsyncSession = request.state.session
        pks_int = [int(pk) for pk in pks]
        if pks_int:
            result = await session.execute(select(User).where(User.id.in_(pks_int)))
            for user in result.scalars().all():
                user.is_shadow_banned = not user.is_shadow_banned
            await session.commit()
        return JSONResponse(content={"message": "Статус теневого бана изменен."})
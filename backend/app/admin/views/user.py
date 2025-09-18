#backend/app/admin/views/user.py
from sqladmin import ModelView, action
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# --- ИСПРАВЛЕНИЕ: Добавлен импорт ---
from app.core.config import settings
from app.db.models import User, LoginHistory, BannedIP, TaskHistory
from sqladmin.filters import AllUniqueStringValuesFilter, BooleanFilter
from app.core.plans import get_limits_for_plan
from app.core.enums import PlanName
from app.core.security import decrypt_data, create_access_token

class UserAdmin(ModelView, model=User):
    identity = "user"
    name_plural = "Пользователи"
    icon = "fa-solid fa-users"
    can_edit = True

    column_list = [
        User.id, User.vk_id, User.plan, User.plan_expires_at, User.is_admin, User.created_at,
    ]
    column_searchable_list = [User.id, User.vk_id]
    column_filters = [AllUniqueStringValuesFilter(User.plan), BooleanFilter(User.is_admin)]
    column_default_sort = ("created_at", True)
 
    form_columns = [
        User.plan, User.plan_expires_at, User.is_admin,
        User.daily_likes_limit, User.daily_add_friends_limit, User.daily_message_limit, User.daily_posts_limit,
    ]
    
    column_formatters = {
        User.plan: lambda m, a: m.plan or "Не указан",
        User.plan_expires_at: lambda m, a: m.plan_expires_at.strftime('%Y-%m-%d %H:%M') if m.plan_expires_at else "Не истекает",
    }

    async def on_model_change(self, data: dict, model: User, is_created: bool, request: Request):
        if 'plan' in data and not is_created:
            original_plan = model.plan
            if data['plan'] != original_plan:
                new_limits = get_limits_for_plan(PlanName(data['plan']))
                for key, value in new_limits.items():
                    if hasattr(model, key):
                        setattr(model, key, value)

    @action(name="impersonate", label="👤 Войти как пользователь", add_in_detail=True, add_in_list=True)
    async def impersonate(self, request: Request, pks: list[int]):
        if len(pks) != 1:
            return JSONResponse({"status": "error", "message": "Выберите одного пользователя."}, status_code=400)
        
        session: AsyncSession = request.state.session
        admin_user_stmt = select(User).where(User.vk_id == int(settings.ADMIN_VK_ID))
        admin = (await session.execute(admin_user_stmt)).scalar_one()
        target_user_id = int(pks[0])

        token_data = {"sub": str(admin.id), "profile_id": str(target_user_id), "scope": "impersonate"}
        access_token = create_access_token(data=token_data, expires_delta=timedelta(minutes=15))
        
        message = f"Токен для входа от имени пользователя ID {target_user_id} создан. Действует 15 минут."
        return JSONResponse({"status": "success", "message": message, "access_token": access_token})

    @action(name="extend_subscription", label="✅ Продлить подписку (+30 дней)", add_in_list=True, add_in_detail=True)
    async def extend_subscription(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        successful_count = 0
        for pk_str in pks:
            user = await session.get(User, int(pk_str))
            if not user: continue

            now = datetime.now(timezone.utc)
            start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > now else now
            user.plan_expires_at = start_date + timedelta(days=30)

            if user.plan == PlanName.EXPIRED.name:
                user.plan = PlanName.PLUS.name
                new_limits = get_limits_for_plan(PlanName.PLUS)
                for k, v in new_limits.items():
                    if hasattr(user, k): setattr(user, k, v)
            successful_count += 1
        await session.commit()
        return {"message": f"Подписка продлена для {successful_count} пользователей."}

    @action(name="ban_user_ip", label="🚫 Забанить по IP", confirmation_message="Уверены? Пользователь потеряет доступ к сайту с этого IP.", add_in_list=True, add_in_detail=True)
    async def ban_user_ip(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        banned_count = 0
        
        # --- УЛУЧШЕНИЕ: Получаем реального админа ---
        admin_user_stmt = select(User).where(User.vk_id == int(settings.ADMIN_VK_ID))
        admin = (await session.execute(admin_user_stmt)).scalar_one()

        for pk in pks:
            stmt = select(LoginHistory.ip_address).where(LoginHistory.user_id == int(pk)).order_by(LoginHistory.timestamp.desc()).limit(1)
            last_ip = (await session.execute(stmt)).scalar_one_or_none()
            if not last_ip or last_ip == "unknown": continue
            
            exists_stmt = select(BannedIP).where(BannedIP.ip_address == last_ip)
            if (await session.execute(exists_stmt)).scalar_one_or_none(): continue
                
            new_ban = BannedIP(ip_address=last_ip, reason=f"Блокировка пользователя ID {pk}", admin_id=admin.id)
            session.add(new_ban)
            banned_count += 1
        
        await session.commit()
        return {"message": f"Заблокировано IP-адресов: {banned_count}"}

    @action(name="delete_account", label="❌ Удалить аккаунт", confirmation_message="ВНИМАНИЕ: Это действие необратимо и удалит ВСЕ данные пользователя!", add_in_list=True, add_in_detail=True)
    async def delete_account(self, request: Request, pks: list[int]):
        session: AsyncSession = request.state.session
        deleted_count = 0
        for pk in pks:
            user = await session.get(User, int(pk))
            if user:
                await session.delete(user)
                deleted_count += 1
        await session.commit()
        return {"message": f"Удалено аккаунтов: {deleted_count}"}
# Содержит UserAdmin
from sqladmin import ModelView, action
from app.db.models import User
from datetime import timedelta, datetime, timezone
from fastapi import Request
from sqladmin import ModelView, action
from app.db.models import User
from app.db.session import AsyncSessionFactory
from app.core.plans import get_limits_for_plan

class UserAdmin(ModelView, model=User):
    name_plural = "Пользователи"
    icon = "fa-solid fa-users"
    
    column_list = [
        User.id, User.vk_id, User.plan, User.plan_expires_at,
        User.is_admin, User.created_at
    ]
    column_formatters = {
        User.vk_id: lambda m, a: f'<a href="https://vk.com/id{m.vk_id}" target="_blank">{m.vk_id}</a>'
    }
    column_searchable_list = [User.vk_id, User.id]
    column_filters = [User.plan, User.is_admin]
    column_default_sort = ("created_at", True)
    
    form_columns = [
        User.plan, User.plan_expires_at, User.is_admin, User.daily_likes_limit,
        User.daily_add_friends_limit, User.daily_message_limit, User.daily_posts_limit,
    ]
    
    @action(
        name="extend_subscription", label="Продлить подписку (+30 дней)",
        confirmation_message="Уверены, что хотите продлить подписку на 30 дней?",
        add_in_detail=True, add_in_list=True,
    )
    async def extend_subscription_action(self, request: Request, pks: list[int]):
        async with AsyncSessionFactory() as session:
            for pk in pks:
                user = await session.get(User, pk)
                if not user: continue
                
                start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > datetime.now(timezone.utc) else datetime.now(timezone.utc)
                user.plan_expires_at = start_date + timedelta(days=30)
                
                if user.plan == "Expired":
                    user.plan = "Plus"
                    new_limits = get_limits_for_plan("Plus")
                    for key, value in new_limits.items():
                        setattr(user, key, value)

            await session.commit()
        return {"message": f"Подписка продлена для {len(pks)} пользователей."}
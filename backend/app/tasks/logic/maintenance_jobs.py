# --- backend/app/tasks/logic/maintenance_jobs.py ---
import datetime
import structlog
from sqlalchemy import delete, select, update, or_

from app.db.session import AsyncSessionFactory
from app.db.models import TaskHistory, User, Automation, Notification
from app.core.plans import get_limits_for_plan
from app.core.constants import CronSettings

log = structlog.get_logger(__name__)

async def _clear_old_task_history_async():
    """Удаляет старые записи из TaskHistory согласно настройкам хранения."""
    async with AsyncSessionFactory() as session:
        pro_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=CronSettings.TASK_HISTORY_RETENTION_DAYS_PRO)
        stmt_pro = delete(TaskHistory).where(
            TaskHistory.user_id.in_(select(User.id).filter(User.plan.in_(['PRO', 'Plus', 'Agency']))),
            TaskHistory.created_at < pro_cutoff
        )
        pro_result = await session.execute(stmt_pro)

        base_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=CronSettings.TASK_HISTORY_RETENTION_DAYS_BASE)
        stmt_base = delete(TaskHistory).where(
            TaskHistory.user_id.in_(select(User.id).filter(User.plan.in_(['Базовый', 'Expired']))),
            TaskHistory.created_at < base_cutoff
        )
        base_result = await session.execute(stmt_base)

        await session.commit()
        total_deleted = pro_result.rowcount + base_result.rowcount
        if total_deleted > 0:
            log.info("maintenance.task_history_cleaned", count=total_deleted)

async def _check_expired_plans_async():
    """Проверяет и деактивирует истекшие тарифные планы пользователей."""
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(User).where(User.plan != 'Expired', User.plan_expires_at != None, User.plan_expires_at < now)
        expired_users = (await session.execute(stmt)).scalars().all()

        if not expired_users:
            return

        log.info("maintenance.expired_plans_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan("Expired")
        user_ids_to_deactivate = [user.id for user in expired_users]

        notifications = [Notification(user_id=user.id, message=f"Срок действия тарифа '{user.plan}' истек.", level="error") for user in expired_users]
        session.add_all(notifications)

        await session.execute(update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False))
        await session.execute(update(User).where(User.id.in_(user_ids_to_deactivate)).values(
            plan="Expired",
            daily_likes_limit=expired_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=expired_plan_limits["daily_add_friends_limit"],
            daily_message_limit=expired_plan_limits["daily_message_limit"],
            daily_posts_limit=expired_plan_limits["daily_posts_limit"]
        ))
        await session.commit()
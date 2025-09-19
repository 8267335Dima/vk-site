# app/tasks/logic/maintenance_jobs.py
import datetime
import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from app.db.session import AsyncSessionFactory
from app.db.models import TaskHistory, User, Automation, Notification
from app.core.plans import get_limits_for_plan
from app.core.enums import PlanName
from app.core.constants import CronSettings


log = structlog.get_logger(__name__)

@asynccontextmanager
async def get_session(provided_session: AsyncSession | None = None):
    """Контекстный менеджер для получения сессии БД."""
    if provided_session:
        yield provided_session
    else:
        async with AsyncSessionFactory() as session:
            yield session

async def _clear_old_task_history_async():
    """Удаляет старые записи из TaskHistory согласно настройкам хранения."""
    async with AsyncSessionFactory() as session:
        pro_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=CronSettings.TASK_HISTORY_RETENTION_DAYS_PRO)
        stmt_pro = delete(TaskHistory).where(
            TaskHistory.user_id.in_(select(User.id).filter(User.plan.in_(['PRO', 'PLUS', 'AGENCY']))),
            TaskHistory.created_at < pro_cutoff
        )
        pro_result = await session.execute(stmt_pro)
        
        base_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=CronSettings.TASK_HISTORY_RETENTION_DAYS_BASE)
        stmt_base = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                select(User.id).filter(User.plan.in_([PlanName.BASE.name, PlanName.EXPIRED.name]))
            ),
            TaskHistory.created_at < base_cutoff
        )
        base_result = await session.execute(stmt_base)
        
        await session.commit()
        total_deleted = pro_result.rowcount + base_result.rowcount
        if total_deleted > 0:
            log.info("maintenance.task_history_cleaned", count=total_deleted)

async def _check_expired_plans_async(session_for_test: AsyncSession | None = None):
    """Проверяет и деактивирует истекшие тарифные планы пользователей."""
    async with get_session(session_for_test) as session:
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(User).where(User.plan != 'Expired', User.plan_expires_at != None, User.plan_expires_at < now)
        expired_users = (await session.execute(stmt)).scalars().all()

        if not expired_users:
            return

        log.info("maintenance.expired_plans_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan(PlanName.EXPIRED)
        user_ids_to_deactivate = [user.id for user in expired_users]

        notifications = [Notification(user_id=user.id, message=f"Срок действия тарифа '{user.plan}' истек.", level="error") for user in expired_users]
        session.add_all(notifications)

        await session.execute(update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False))
        
        await session.execute(update(User).where(User.id.in_(user_ids_to_deactivate)).values(
            plan=PlanName.EXPIRED.name,
            **{k: v for k, v in expired_plan_limits.items() if hasattr(User, k)}
        ))
        
        if not session_for_test:
            await session.commit()
        else:
            await session.flush()
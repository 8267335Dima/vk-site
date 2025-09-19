# app/tasks/logic/maintenance_jobs.py
import datetime
import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy.orm import selectinload
from app.db.session import AsyncSessionFactory
from app.db.models import TaskHistory, User, Automation, Notification
from app.core.plans import get_limits_for_plan
from app.core.enums import PlanName
from app.core.constants import CronSettings
from app.db.models.payment import Plan


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

async def _check_expired_plans_async(session: AsyncSession | None = None):
    """Проверяет и деактивирует истекшие тарифные планы пользователей."""
    async with get_session(session) as db_session:
        now = datetime.datetime.now(datetime.UTC)

        # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
        expired_plan_stmt = select(Plan.id).where(Plan.name_id == PlanName.EXPIRED.name)
        expired_plan_id = (await db_session.execute(expired_plan_stmt)).scalar_one_or_none()

        # Если системный тариф 'Expired' не найден в БД, это критическая ошибка конфигурации.
        # Задача не может продолжать работу.
        if not expired_plan_id:
            log.critical("maintenance.fatal_error", message="Expired plan not found in the database. Cannot process expired users.")
            return
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
        
        stmt = select(User).where(
            User.plan_id != expired_plan_id,
            User.plan_expires_at != None,
            User.plan_expires_at < now
        ).options(selectinload(User.plan)) # Добавил selectinload для оптимизации
        
        expired_users = (await db_session.execute(stmt)).scalars().unique().all()

        if not expired_users:
            return

        log.info("maintenance.expired_plans_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan(PlanName.EXPIRED)
        user_ids_to_deactivate = [user.id for user in expired_users]

        notifications = [
            Notification(
                user_id=user.id,
                message=f"Срок действия тарифа '{user.plan.display_name if user.plan else 'Unknown'}' истек.",
                level="error"
            ) for user in expired_users
        ]
        db_session.add_all(notifications)

        await db_session.execute(
            update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False)
        )

        await db_session.execute(
            update(User).where(User.id.in_(user_ids_to_deactivate)).values(
                plan_id=expired_plan_id,
                **{k: v for k, v in expired_plan_limits.items() if hasattr(User, k)}
            )
        )

        if not session:
            await db_session.commit()
        else:
            await db_session.flush()
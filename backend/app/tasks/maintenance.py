# backend/app/tasks/maintenance.py
import datetime
import structlog
from sqlalchemy import delete, select

# Импорты Celery удалены
from app.db.session import AsyncSessionFactory
from app.db.models import TaskHistory, User

log = structlog.get_logger(__name__)

async def _clear_old_task_history_async():
    async with AsyncSessionFactory() as session:
        # Удаляем записи старше 90 дней для платных тарифов
        pro_plus_cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=90)
        stmt_pro = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                select(User.id).filter(User.plan.in_(['PRO', 'Plus', 'Agency']))
            ),
            TaskHistory.created_at < pro_plus_cutoff
        )
        pro_result = await session.execute(stmt_pro)

        # Удаляем записи старше 30 дней для Базового и Истекшего
        base_cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        stmt_base = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                select(User.id).filter(User.plan.in_(['Базовый', 'Expired']))
            ),
            TaskHistory.created_at < base_cutoff
        )
        base_result = await session.execute(stmt_base)

        await session.commit()
        total_deleted = pro_result.rowcount + base_result.rowcount
        log.info("maintenance.task_history_cleaned", count=total_deleted)

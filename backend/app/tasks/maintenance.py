# backend/app/tasks/maintenance.py
import datetime
from celery import shared_task
from sqlalchemy import delete
from app.db.session import AsyncSessionFactory
from app.db.models import ActionLog
import structlog

log = structlog.get_logger(__name__)

@shared_task(name="app.tasks.maintenance.clear_old_action_logs")
async def clear_old_action_logs():
    """
    Удаляет записи из ActionLog старше 90 дней, чтобы предотвратить
    бесконечное разрастание таблицы.
    """
    async with AsyncSessionFactory() as session:
        ninety_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=90)

        stmt = delete(ActionLog).where(ActionLog.timestamp < ninety_days_ago)
        result = await session.execute(stmt)
        await session.commit()

        log.info("maintenance.logs_cleaned", count=result.rowcount)
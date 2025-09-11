# backend/app/tasks/maintenance.py
import datetime
import asyncio # --- НОВЫЙ ИМПОРТ ---
from celery import shared_task
from sqlalchemy import delete
from app.db.session import AsyncSessionFactory
from app.db.models import ActionLog
import structlog

log = structlog.get_logger(__name__)

async def _clear_old_action_logs_async():
    """Асинхронная логика очистки логов."""
    async with AsyncSessionFactory() as session:
        ninety_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=90)
        stmt = delete(ActionLog).where(ActionLog.timestamp < ninety_days_ago)
        result = await session.execute(stmt)
        await session.commit()
        log.info("maintenance.logs_cleaned", count=result.rowcount)

@shared_task(name="app.tasks.maintenance.clear_old_action_logs")
def clear_old_action_logs():
    """Синхронная задача-обертка для Celery."""
    asyncio.run(_clear_old_action_logs_async())
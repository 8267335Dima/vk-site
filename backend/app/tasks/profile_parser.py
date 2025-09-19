# backend/app/tasks/profile_parser.py
import asyncio
import structlog
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, UTC

from app.db.models import User
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.services.vk_api import VKAuthError
from app.tasks.logic.maintenance_jobs import get_session
# <--- ИЗМЕНЕНИЕ 1: Добавляем импорт SystemLogEmitter
from app.services.event_emitter import SystemLogEmitter

log = structlog.get_logger(__name__)


async def _snapshot_all_users_metrics_async(session: AsyncSession | None = None):
    """
    Создает "снимок" метрик для всех активных пользователей.
    Может принимать существующую сессию БД для целей тестирования.
    """
    async with get_session(session) as db_session:
        now = datetime.now(UTC)
        
        stmt = (
            select(User)
            .options(selectinload(User.proxies))
            .where(or_(User.plan_expires_at == None, User.plan_expires_at > now))
        )
        
        result = await db_session.execute(stmt)
        active_users = result.scalars().unique().all()

        if not active_users:
            log.info("snapshot_metrics_task.no_active_users")
            return

        log.info("snapshot_metrics_task.start", count=len(active_users))

        for user in active_users:
            try:
                emitter = SystemLogEmitter("snapshot_metrics")
                emitter.set_context(user.id) # Привязываем логгер к пользователю
                
                service = ProfileAnalyticsService(db=db_session, user=user, emitter=emitter)
                
                await service.snapshot_profile_metrics()
            except VKAuthError:
                log.warn("snapshot_metrics_task.auth_error", user_id=user.id)
            except Exception as e:
                log.error("snapshot_metrics_task.user_error", user_id=user.id, error=str(e))

        log.info("snapshot_metrics_task.finished")
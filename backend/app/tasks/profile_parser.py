# backend/app/tasks/profile_parser.py

import asyncio
import datetime  # <--- ИСПРАВЛЕНИЕ: Добавлен этот импорт
import structlog
from celery import shared_task
from sqlalchemy import select

from app.db.session import AsyncSessionFactory
from app.db.models import User 
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.services.vk_api import VKAuthError

log = structlog.get_logger(__name__)

@shared_task(name="app.tasks.profile_parser.snapshot_all_users_metrics")
async def snapshot_all_users_metrics():
    """
    Периодическая задача для сбора метрик роста для всех активных пользователей.
    Запускается один раз в сутки.
    """
    async with AsyncSessionFactory() as session:
        # Используем .utcnow() для консистентности
        stmt = select(User).where(User.plan_expires_at > datetime.datetime.utcnow())
        result = await session.execute(stmt)
        active_users = result.scalars().all()

        if not active_users:
            log.info("snapshot_metrics_task.no_active_users")
            return

        log.info("snapshot_metrics_task.start", count=len(active_users))
        
        tasks = []
        for user in active_users:
            task = asyncio.create_task(_process_user(user))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        log.info("snapshot_metrics_task.finished")

async def _process_user(user: User):
    """Изолированная логика обработки одного пользователя."""
    async with AsyncSessionFactory() as user_session:
        try:
            # emitter не нужен для фоновой задачи
            service = ProfileAnalyticsService(db=user_session, user=user, emitter=None)
            await service.snapshot_profile_metrics()
        except VKAuthError:
            log.warn("snapshot_metrics_task.auth_error", user_id=user.id)
            # Здесь можно добавить логику отправки уведомления пользователю о невалидном токене
        except Exception as e:
            log.error("snapshot_metrics_task.user_error", user_id=user.id, error=str(e))
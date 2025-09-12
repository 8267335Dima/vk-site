# backend/app/tasks/profile_parser.py
import asyncio
import datetime
import structlog
from sqlalchemy import select, or_

from app.celery_app import celery_app
from celery import Task

from app.db.session import AsyncSessionFactory
from app.db.models import User 
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.services.vk_api import VKAuthError
from app.tasks.utils import run_async_from_sync

log = structlog.get_logger(__name__)

async def _snapshot_all_users_metrics_async():
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        stmt = select(User).where(or_(User.plan_expires_at == None, User.plan_expires_at > now))
        result = await session.execute(stmt)
        active_users = result.scalars().all()

        if not active_users:
            log.info("snapshot_metrics_task.no_active_users")
            return

        log.info("snapshot_metrics_task.start", count=len(active_users))
        
        tasks = [_process_user(user) for user in active_users]
        await asyncio.gather(*tasks)
        
        log.info("snapshot_metrics_task.finished")

async def _process_user(user: User):
    async with AsyncSessionFactory() as user_session:
        try:
            service = ProfileAnalyticsService(db=user_session, user=user, emitter=None)
            await service.snapshot_profile_metrics()
        except VKAuthError:
            log.warn("snapshot_metrics_task.auth_error", user_id=user.id)
        except Exception as e:
            log.error("snapshot_metrics_task.user_error", user_id=user.id, error=str(e))

@celery_app.task(name="app.tasks.profile_parser.snapshot_all_users_metrics")
def snapshot_all_users_metrics():
    run_async_from_sync(_snapshot_all_users_metrics_async())
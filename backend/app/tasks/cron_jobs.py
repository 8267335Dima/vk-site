import structlog
from redis.asyncio import Redis
from sqlalchemy import select
from app.db.models import User

from app.tasks.logic.analytics_jobs import (
    _aggregate_daily_stats_async,
    _generate_all_heatmaps_async,
    _update_friend_request_statuses_async,
    _process_user_notifications_async  # Добавляем новый обработчик
)
from app.tasks.logic.maintenance_jobs import _check_expired_plans_async
from app.tasks.logic.automation_jobs import _run_daily_automations_async
from app.db.session import AsyncSessionFactory
from app.core.config import settings
from app.core.config_loader import APP_SETTINGS  # <-- Правильный импорт настроек

log = structlog.get_logger(__name__)


async def aggregate_daily_stats_job(ctx):
    async with AsyncSessionFactory() as session:
        await _aggregate_daily_stats_async(session=session)


async def snapshot_all_users_metrics_job(ctx):
    log.info("cron.dispatcher.snapshot_metrics.start")
    async with AsyncSessionFactory() as session:
        active_users_ids_result = await session.execute(
            select(User.id).where(User.is_deleted == False)
        )
        user_ids = active_users_ids_result.scalars().all()
        if not user_ids:
            log.info("cron.dispatcher.snapshot_metrics.no_users")
            return
        for user_id in user_ids:
            await ctx['redis_pool'].enqueue_job(
                "snapshot_single_user_metrics_task",
                user_id=user_id,
                _queue_name='low_priority'
            )
        log.info("cron.dispatcher.snapshot_metrics.enqueued", count=len(user_ids))


async def check_expired_plans_job(ctx):
    async with AsyncSessionFactory() as session:
        await _check_expired_plans_async(session=session)


async def generate_all_heatmaps_job(ctx):
    async with AsyncSessionFactory() as session:
        await _generate_all_heatmaps_async(session=session)


async def update_friend_request_statuses_job(ctx):
    async with AsyncSessionFactory() as session:
        await _update_friend_request_statuses_async(session=session)


# Новая крон-задача для регулярной обработки уведомлений
async def process_user_notifications_job(ctx):
    async with AsyncSessionFactory() as session:
        await _process_user_notifications_async(session=session)


async def run_standard_automations_job(ctx):
    redis_lock_client = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
    lock_key = "lock:task:run_automations:standard"
    # Используем настройки из APP_SETTINGS
    if not await redis_lock_client.set(lock_key, "1", ex=APP_SETTINGS.cron.automation_job_lock_seconds, nx=True):
        await redis_lock_client.close()
        return
    try:
        async with AsyncSessionFactory() as session:
            await _run_daily_automations_async(session, ctx['redis_pool'], automation_group='standard')
    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()


async def run_online_automations_job(ctx):
    redis_lock_client = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
    lock_key = "lock:task:run_automations:online"
    # Используем настройки из APP_SETTINGS
    if not await redis_lock_client.set(lock_key, "1", ex=APP_SETTINGS.cron.automation_job_lock_seconds, nx=True):
        await redis_lock_client.close()
        return
    try:
        async with AsyncSessionFactory() as session:
            await _run_daily_automations_async(session, ctx['redis_pool'], automation_group='online')
    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()
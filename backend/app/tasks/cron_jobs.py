# --- backend/app/tasks/cron_jobs.py ---
import structlog
from redis.asyncio import Redis

from app.tasks.logic.analytics_jobs import (
    _aggregate_daily_stats_async,
    _generate_all_heatmaps_async,
    _update_friend_request_statuses_async,
    _snapshot_all_users_metrics_async
)
from app.tasks.logic.maintenance_jobs import _check_expired_plans_async
from app.tasks.logic.automation_jobs import _run_daily_automations_async
from app.db.session import AsyncSessionFactory
from app.core.config import settings
from app.core.constants import CronSettings

log = structlog.get_logger(__name__)

# --- ИЗМЕНЕНИЕ: Все функции теперь создают сессию и передают ее в логику ---

async def aggregate_daily_stats_job(ctx):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            await _aggregate_daily_stats_async(session=session)

async def snapshot_all_users_metrics_job(ctx):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            await _snapshot_all_users_metrics_async(session=session)

async def check_expired_plans_job(ctx):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            await _check_expired_plans_async(session=session)

async def generate_all_heatmaps_job(ctx):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            await _generate_all_heatmaps_async(session=session)

async def update_friend_request_statuses_job(ctx):
    async with AsyncSessionFactory() as session:
        async with session.begin():
            await _update_friend_request_statuses_async(session=session)

async def run_standard_automations_job(ctx):
    redis_lock_client = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
    lock_key = "lock:task:run_automations:standard"
    if not await redis_lock_client.set(lock_key, "1", ex=CronSettings.AUTOMATION_JOB_LOCK_EXPIRATION_SECONDS, nx=True):
        await redis_lock_client.close()
        return

    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                await _run_daily_automations_async(session, ctx['redis_pool'], automation_group='standard')
    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()

async def run_online_automations_job(ctx):
    redis_lock_client = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
    lock_key = "lock:task:run_automations:online"
    if not await redis_lock_client.set(lock_key, "1", ex=CronSettings.AUTOMATION_JOB_LOCK_EXPIRATION_SECONDS, nx=True):
        await redis_lock_client.close()
        return

    try:
        async with AsyncSessionFactory() as session:
            async with session.begin():
                await _run_daily_automations_async(session, ctx['redis_pool'], automation_group='online')
    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()
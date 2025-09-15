# backend/app/tasks/cron_jobs.py
from app.tasks.cron import (
    _aggregate_daily_stats_async,
    _check_expired_plans_async,
    _generate_all_heatmaps_async,
    _update_friend_request_statuses_async,
    _run_daily_automations_async
)

async def aggregate_daily_stats_job(ctx):
    await _aggregate_daily_stats_async()

async def check_expired_plans_job(ctx):
    await _check_expired_plans_async()

async def generate_all_heatmaps_job(ctx):
    await _generate_all_heatmaps_async()

async def update_friend_request_statuses_job(ctx):
    await _update_friend_request_statuses_async()

# Эта задача заменит несколько старых задач Celery
async def run_standard_automations_job(ctx):
    await _run_daily_automations_async(automation_group='standard')

async def run_online_automations_job(ctx):
    await _run_daily_automations_async(automation_group='online')
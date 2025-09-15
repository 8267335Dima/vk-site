# backend/app/tasks/profile_parser_jobs.py
from app.tasks.profile_parser import _snapshot_all_users_metrics_async

async def snapshot_all_users_metrics_job(ctx):
    await _snapshot_all_users_metrics_async()
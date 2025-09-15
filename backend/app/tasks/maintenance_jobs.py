# backend/app/tasks/maintenance_jobs.py
from app.tasks.maintenance import _clear_old_task_history_async

async def clear_old_task_history_job(ctx):
    await _clear_old_task_history_async()
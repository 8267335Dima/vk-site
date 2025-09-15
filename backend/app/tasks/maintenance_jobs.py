# --- backend/app/tasks/maintenance_jobs.py ---
from app.tasks.logic.maintenance_jobs import _clear_old_task_history_async

async def clear_old_task_history_job(ctx):
    """ARQ-задача для очистки старой истории задач."""
    await _clear_old_task_history_async()
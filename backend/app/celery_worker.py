# backend/app/celery_worker.py
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings
from app.tasks.cron import (
    run_daily_automations, check_expired_plans, 
    aggregate_daily_stats, snapshot_all_users_friends_count # <-- ДОБАВЛЕНО
)

redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.runner",
        "app.tasks.cron",
        "app.tasks.maintenance"
    ] 
)

celery_app.conf.task_routes = {
    'app.tasks.cron.*': {'queue': 'default'},
    'app.tasks.maintenance.*': {'queue': 'low_priority'},
}

celery_app.conf.update(
    task_track_started=True,
    task_default_queue='default',
    beat_dburi=settings.database_url.replace("+asyncpg", ""),
)

# --- ИЗМЕНЕННЫЙ ИМПОРТ ---
from app.tasks.cron import run_daily_automations, check_expired_plans, aggregate_daily_stats
from app.tasks.maintenance import clear_old_action_logs

# Статически добавляем системные задачи в расписание
celery_app.add_periodic_task(
    crontab(hour=2, minute=5), # Изменим время, чтобы не конфликтовать
    aggregate_daily_stats.s(),
    name='aggregate-daily-stats-every-night'
)

celery_app.add_periodic_task(
    crontab(hour=3, minute=0), # Например, в 3 часа ночи
    snapshot_all_users_friends_count.s(),
    name='snapshot-friends-count-daily'
)

celery_app.add_periodic_task(
    crontab(minute='*/30'),
    run_daily_automations.s(),
    name='run-automations-scheduler'
)
celery_app.add_periodic_task(
    crontab(minute='*/15'),
    check_expired_plans.s(), # <-- Теперь эта задача существует и будет выполняться
    name='check-expired-plans-scheduler'
)
celery_app.add_periodic_task(
    crontab(hour=4, minute=0),
    clear_old_action_logs.s(),
    name='clear-old-logs-daily'
)
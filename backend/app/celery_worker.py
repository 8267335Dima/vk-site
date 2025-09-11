# backend/app/celery_worker.py
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.runner.v2",
        "app.tasks.cron",
        "app.tasks.maintenance",
        "app.tasks.profile_parser" # НОВЫЙ
    ] 
)

celery_app.conf.task_routes = {
    'app.tasks.cron.*': {'queue': 'default'},
    'app.tasks.maintenance.*': {'queue': 'low_priority'},
    'app.tasks.profile_parser.*': {'queue': 'low_priority'}, # НОВЫЙ
}

celery_app.conf.update(
    task_track_started=True,
    task_default_queue='default',
    beat_dburi=settings.database_url.replace("+asyncpg", ""),
)

# Импорты периодических задач
from app.tasks.cron import (
    run_daily_automations, check_expired_plans, aggregate_daily_stats
)
from app.tasks.maintenance import clear_old_task_history
from app.tasks.profile_parser import snapshot_all_users_metrics

# --- РАСПИСАНИЕ CRON-ЗАДАЧ ---

# Каждый день в 2 часа ночи: агрегируем статистику за вчера
celery_app.add_periodic_task(
    crontab(hour=2, minute=5),
    aggregate_daily_stats.s(),
    name='aggregate-daily-stats'
)

# Каждый день в 3 часа ночи: собираем метрики роста для всех пользователей
celery_app.add_periodic_task(
    crontab(hour=3, minute=0),
    snapshot_all_users_metrics.s(),
    name='snapshot-profile-metrics'
)

# Каждый день в 4 часа ночи: чистим старую историю задач
celery_app.add_periodic_task(
    crontab(hour=4, minute=0),
    clear_old_task_history.s(),
    name='clear-old-task-history'
)

# Каждые 15 минут: проверяем истекшие тарифы
celery_app.add_periodic_task(
    crontab(minute='*/15'),
    check_expired_plans.s(),
    name='check-expired-plans'
)

# Каждые 5 минут: запускаем обычные автоматизации (лайки, добавления и т.д.)
# (сама логика внутри задачи решает, кого и когда запускать)
celery_app.add_periodic_task(
    crontab(minute='*/5'),
    run_daily_automations.s(automation_group='standard'),
    name='run-standard-automations'
)

# Каждые 10 минут: запускаем автоматизацию "вечный онлайн"
celery_app.add_periodic_task(
    crontab(minute='*/10'),
    run_daily_automations.s(automation_group='online'),
    name='run-online-automations'
)
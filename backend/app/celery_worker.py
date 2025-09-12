# backend/app/celery_worker.py
from celery.schedules import crontab
# --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Импортируем уже настроенный экземпляр ---
from app.celery_app import celery_app

# Импорты периодических задач (они нужны, чтобы beat их увидел)
from app.tasks.cron import (
    run_daily_automations, check_expired_plans, aggregate_daily_stats
)
from app.tasks.maintenance import clear_old_action_logs
from app.tasks.profile_parser import snapshot_all_users_metrics

# --- РАСПИСАНИЕ CRON-ЗАДАЧ ---
# Мы просто добавляем задачи в уже импортированный и настроенный celery_app

celery_app.add_periodic_task(
    crontab(hour=2, minute=5),
    aggregate_daily_stats.s(),
    name='aggregate-daily-stats'
)

celery_app.add_periodic_task(
    crontab(hour=3, minute=0),
    snapshot_all_users_metrics.s(),
    name='snapshot-profile-metrics'
)

celery_app.add_periodic_task(
    crontab(hour=4, minute=0),
    clear_old_action_logs.s(),
    name='clear-old-action-logs'
)

celery_app.add_periodic_task(
    crontab(minute='*/15'),
    check_expired_plans.s(),
    name='check-expired-plans'
)

celery_app.add_periodic_task(
    crontab(minute='*/5'),
    run_daily_automations.s(automation_group='standard'),
    name='run-standard-automations'
)

celery_app.add_periodic_task(
    crontab(minute='*/10'),
    run_daily_automations.s(automation_group='online'),
    name='run-online-automations'
)
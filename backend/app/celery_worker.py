# backend/app/celery_worker.py
from celery.schedules import crontab
from app.celery_app import celery_app

from app.tasks import runner
from app.tasks import cron
from app.tasks import maintenance
from app.tasks import profile_parser


celery_app.add_periodic_task(
    crontab(hour=2, minute=5),
    cron.aggregate_daily_stats.s(),
    name='aggregate-daily-stats'
)

celery_app.add_periodic_task(
    crontab(hour=3, minute=0),
    profile_parser.snapshot_all_users_metrics.s(),
    name='snapshot-profile-metrics'
)

celery_app.add_periodic_task(
    crontab(hour=4, minute=0),
    maintenance.clear_old_task_history.s(),
    name='clear-old-task-history'
)

celery_app.add_periodic_task(
    crontab(minute='*/15'),
    cron.check_expired_plans.s(),
    name='check-expired-plans'
)

celery_app.add_periodic_task(
    crontab(minute='*/5'),
    cron.run_daily_automations.s(automation_group='standard'),
    name='run-standard-automations'
)

celery_app.add_periodic_task(
    crontab(minute='*/10'),
    cron.run_daily_automations.s(automation_group='online'),
    name='run-online-automations'
)
# --- backend/app/celery_worker.py ---
from celery.schedules import crontab
from app.celery_app import celery_app

from app.tasks import runner
from app.tasks import cron
from app.tasks import maintenance
from app.tasks import profile_parser

# Jitter (в секундах) добавляет случайную задержку к запуску, 
# чтобы избежать одновременного старта задач на всех воркерах ("Thundering Herd").
JITTER_MEDIUM = 60
JITTER_LOW = 120

celery_app.add_periodic_task(
    crontab(hour=2, minute=5),
    cron.aggregate_daily_stats.s(),
    name='aggregate-daily-stats',
    options={'jitter': JITTER_MEDIUM}
)

celery_app.add_periodic_task(
    crontab(hour=3, minute=0),
    profile_parser.snapshot_all_users_metrics.s(),
    name='snapshot-profile-metrics',
    options={'jitter': JITTER_LOW}
)

celery_app.add_periodic_task(
    crontab(hour=4, minute=0),
    maintenance.clear_old_task_history.s(),
    name='clear-old-task-history',
    options={'jitter': JITTER_LOW}
)

celery_app.add_periodic_task(
    crontab(hour='*/4', minute=0),
    cron.update_friend_request_statuses.s(),
    name='update-friend-request-statuses',
    options={'jitter': JITTER_LOW}
)

celery_app.add_periodic_task(
    crontab(hour=5, minute=0), 
    cron.generate_all_heatmaps.s(),
    name='generate-all-post-activity-heatmaps',
    options={'jitter': JITTER_LOW}
)

celery_app.add_periodic_task(
    crontab(minute='*/15'),
    cron.check_expired_plans.s(),
    name='check-expired-plans',
    options={'jitter': JITTER_MEDIUM}
)

celery_app.add_periodic_task(
    crontab(minute='*/5'),
    cron.run_daily_automations.s(automation_group='standard'),
    name='run-standard-automations',
    options={'jitter': JITTER_MEDIUM}
)

celery_app.add_periodic_task(
    crontab(minute='*/10'),
    cron.run_daily_automations.s(automation_group='online'),
    name='run-online-automations',
    options={'jitter': JITTER_MEDIUM}
)
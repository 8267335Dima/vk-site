# backend/app/worker.py
import asyncio
from arq import cron
from arq.connections import create_pool

# Импортируем настройки из нового центрального файла
from app.arq_config import redis_settings

# Импортируем асинхронные функции, которые будут нашими задачами
from app.tasks.cron_jobs import (
    aggregate_daily_stats_job,
    check_expired_plans_job,
    generate_all_heatmaps_job,
    update_friend_request_statuses_job,
    run_standard_automations_job,
    run_online_automations_job,
)
from app.tasks.maintenance_jobs import clear_old_task_history_job
from app.tasks.profile_parser_jobs import snapshot_all_users_metrics_job
from app.tasks.main_tasks import (
    like_feed_task,
    add_recommended_friends_task,
    accept_friend_requests_task,
    remove_friends_by_criteria_task,
    view_stories_task,
    birthday_congratulation_task,
    mass_messaging_task,
    eternal_online_task,
    leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
    publish_scheduled_post_task,
    run_scenario_from_scheduler_task,
)

functions = [
    like_feed_task,
    add_recommended_friends_task,
    accept_friend_requests_task,
    remove_friends_by_criteria_task,
    view_stories_task,
    birthday_congratulation_task,
    mass_messaging_task,
    eternal_online_task,
    leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
    publish_scheduled_post_task,
    run_scenario_from_scheduler_task,
]

cron_jobs = [
    cron(aggregate_daily_stats_job, hour=2, minute=5),
    cron(snapshot_all_users_metrics_job, hour=3),
    cron(clear_old_task_history_job, hour=4),
    cron(update_friend_request_statuses_job, hour='*/4'), # каждые 4 часа
    cron(generate_all_heatmaps_job, hour=5),
    cron(check_expired_plans_job, minute='*/15'), # каждые 15 минут
    cron(run_standard_automations_job, minute='*/5'), # каждые 5 минут
    cron(run_online_automations_job, minute='*/10'), # каждые 10 минут
]

# Улучшение: передаем пул соединений Redis через контекст,
# чтобы не создавать его в каждой задаче заново.
async def startup(ctx):
    print("Воркер ARQ запущен и готов к работе.")
    ctx['redis_pool'] = await create_pool(redis_settings)

async def shutdown(ctx):
    await ctx['redis_pool'].close()
    print("Воркер ARQ остановлен.")

class WorkerSettings:
    functions = functions
    cron_jobs = cron_jobs
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown
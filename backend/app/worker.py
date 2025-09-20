from arq import cron
from app.arq_config import redis_settings

from app.tasks.cron_jobs import (
    aggregate_daily_stats_job, snapshot_all_users_metrics_job, check_expired_plans_job,
    generate_all_heatmaps_job, update_friend_request_statuses_job, process_user_notifications_job,
    run_standard_automations_job, run_online_automations_job
)
from app.tasks.logic.analytics_jobs import _generate_effectiveness_report_async
from app.tasks.maintenance_jobs import clear_old_task_history_job
from app.tasks.profile_parser_jobs import snapshot_single_user_metrics_task
from app.tasks.standard_tasks import (
    like_feed_task, add_recommended_friends_task, accept_friend_requests_task,
    remove_friends_by_criteria_task, view_stories_task, birthday_congratulation_task,
    mass_messaging_task, eternal_online_task, leave_groups_by_criteria_task,
    join_groups_by_criteria_task
)
from app.tasks.system_tasks import publish_scheduled_post_task, run_scenario_from_scheduler_task

functions = [
    like_feed_task, add_recommended_friends_task, accept_friend_requests_task,
    remove_friends_by_criteria_task, view_stories_task, birthday_congratulation_task,
    mass_messaging_task, eternal_online_task, leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
    publish_scheduled_post_task, run_scenario_from_scheduler_task,
    snapshot_single_user_metrics_task,
    _generate_effectiveness_report_async.func,
]

cron_jobs = [
    cron(aggregate_daily_stats_job, hour=2, minute=5),
    cron(snapshot_all_users_metrics_job, hour=3),
    cron(clear_old_task_history_job, hour=4),
    cron(update_friend_request_statuses_job, hour={0, 4, 8, 12, 16, 20}, minute=0),
    cron(generate_all_heatmaps_job, hour=5),
    cron(check_expired_plans_job, minute={0, 15, 30, 45}),
    cron(process_user_notifications_job, minute=set(range(0, 60, 10))),
    cron(run_standard_automations_job, minute=set(range(0, 60, 5))),
    cron(run_online_automations_job, minute={0, 10, 20, 30, 40, 50}),
]

async def startup(ctx):
    from arq.connections import create_pool
    ctx['redis_pool'] = await create_pool(redis_settings)
    print("Воркер ARQ запущен и готов к работе.")

async def shutdown(ctx):
    if 'redis_pool' in ctx: await ctx['redis_pool'].close()
    print("Воркер ARQ остановлен.")

class WorkerSettings:
    functions = functions
    cron_jobs = cron_jobs
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown
    on_job_failure = "arq.jobs.Job.enqueue_to_dlq"
    queues = ('high_priority', 'arq:queue', 'low_priority')
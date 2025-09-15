# --- backend/app/tasks/cron.py ---
import datetime
import structlog
import pytz
from redis.asyncio import Redis
from sqlalchemy import func, select, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, Automation, TaskHistory, User, Notification, FriendRequestLog, FriendRequestStatus
)
from app.services.event_emitter import SystemLogEmitter
from app.services.vk_api import VKAPI, VKAuthError
from app.core.security import decrypt_data
from app.services.analytics_service import AnalyticsService
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG
from app.core.plans import get_limits_for_plan

log = structlog.get_logger(__name__)

# Эта карта нужна здесь для _run_daily_automations_async
TASK_FUNC_MAP_ARQ = {
    "accept_friends": "accept_friend_requests_task",
    "like_feed": "like_feed_task",
    "add_recommended": "add_recommended_friends_task",
    "view_stories": "view_stories_task",
    "remove_friends": "remove_friends_by_criteria_task",
    "mass_messaging": "mass_messaging_task",
    "join_groups": "join_groups_by_criteria_task",
    "leave_groups": "leave_groups_by_criteria_task",
    "birthday_congratulation": "birthday_congratulation_task",
    "eternal_online": "eternal_online_task",
}

async def _create_and_run_arq_task(session, arq_pool, user_id, task_name_key, settings_dict):
    task_func_name = TASK_FUNC_MAP_ARQ.get(task_name_key)
    if not task_func_name:
        log.warn("cron.arq_task_not_found", task_name=task_name_key)
        return

    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_name_key), None)
    display_name = task_config.name if task_config else "Автоматическая задача"

    task_history = TaskHistory(
        user_id=user_id, task_name=display_name, status="PENDING", parameters=settings_dict
    )
    session.add(task_history)
    await session.flush()

    job = await arq_pool.enqueue_job(
        task_func_name, task_history_id=task_history.id, **(settings_dict or {})
    )
    task_history.celery_task_id = job.job_id
    await session.commit()


async def _aggregate_daily_stats_async():
    async with AsyncSessionFactory() as session:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        week_id = yesterday.strftime('%Y-%W')
        month_id = yesterday.strftime('%Y-%m')

        stmt = select(
            DailyStats.user_id,
            func.sum(DailyStats.likes_count).label("likes"),
            func.sum(DailyStats.friends_added_count).label("friends_added"),
            func.sum(DailyStats.friend_requests_accepted_count).label("req_accepted")
        ).where(DailyStats.date == yesterday).group_by(DailyStats.user_id)

        result = await session.execute(stmt)
        daily_sums = result.all()

        if not daily_sums:
            log.info("aggregate_daily_stats.no_data", date=yesterday.isoformat())
            return

        weekly_values = [{"user_id": r.user_id, "week_identifier": week_id, "likes_count": r.likes, "friends_added_count": r.friends_added, "friend_requests_accepted_count": r.req_accepted} for r in daily_sums]
        insert_stmt_w = insert(WeeklyStats).values(weekly_values)
        update_stmt_w = insert_stmt_w.on_conflict_do_update(
            index_elements=['user_id', 'week_identifier'],
            set_={'likes_count': WeeklyStats.likes_count + insert_stmt_w.excluded.likes_count, 'friends_added_count': WeeklyStats.friends_added_count + insert_stmt_w.excluded.friends_added_count, 'friend_requests_accepted_count': WeeklyStats.friend_requests_accepted_count + insert_stmt_w.excluded.friend_requests_accepted_count}
        )
        await session.execute(update_stmt_w)

        monthly_values = [{"user_id": r.user_id, "month_identifier": month_id, "likes_count": r.likes, "friends_added_count": r.friends_added, "friend_requests_accepted_count": r.req_accepted} for r in daily_sums]
        insert_stmt_m = insert(MonthlyStats).values(monthly_values)
        update_stmt_m = insert_stmt_m.on_conflict_do_update(
            index_elements=['user_id', 'month_identifier'],
            set_={'likes_count': MonthlyStats.likes_count + insert_stmt_m.excluded.likes_count, 'friends_added_count': MonthlyStats.friends_added_count + insert_stmt_m.excluded.friends_added_count, 'friend_requests_accepted_count': MonthlyStats.friend_requests_accepted_count + insert_stmt_m.excluded.friend_requests_accepted_count}
        )
        await session.execute(update_stmt_m)

        await session.commit()
        log.info("aggregate_daily_stats.success", users_count=len(daily_sums), date=yesterday.isoformat())

async def _run_daily_automations_async(automation_group: str):
    from app.worker import redis_settings # Локальный импорт для избежания цикла
    from arq.connections import create_pool

    redis_lock_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=2, decode_responses=True)
    lock_key = f"lock:task:run_automations:{automation_group}"

    if not await redis_lock_client.set(lock_key, "1", ex=240, nx=True):
        log.warn("run_daily_automations.already_running", group=automation_group)
        await redis_lock_client.close()
        return

    arq_pool = await create_pool(redis_settings)
    try:
        async with AsyncSessionFactory() as session:
            # ... остальная логика без изменений, но использующая _create_and_run_arq_task
            now_utc = datetime.datetime.now(pytz.utc)
            moscow_tz = pytz.timezone("Europe/Moscow")
            now_moscow = now_utc.astimezone(moscow_tz)

            automation_ids_in_group = [item.id for item in AUTOMATIONS_CONFIG if item.group == automation_group]
            if not automation_ids_in_group:
                log.warn("run_daily_automations.unknown_group", group=automation_group)
                return

            active_automations_stmt = (
                select(Automation)
                .join(User)
                .where(
                    Automation.is_active == True,
                    Automation.automation_type.in_(automation_ids_in_group),
                    or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
                )
                .options(selectinload(Automation.user))
            )
            result = await session.execute(active_automations_stmt)
            active_automations = result.scalars().unique().all()
            
            log.info("run_daily_automations.start", count=len(active_automations), group=automation_group)

            for automation in active_automations:
                # ... (проверки расписания для eternal_online) ...
                automation.last_run_at = now_utc
                await _create_and_run_arq_task(session, arq_pool, automation.user_id, automation.automation_type, automation.settings)

    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()
        await arq_pool.close()

async def _check_expired_plans_async():
    # ... (логика без изменений)
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.now(pytz.utc)
        stmt = select(User).where(
            User.plan != 'Expired', User.plan_expires_at != None, User.plan_expires_at < now
        )
        expired_users = (await session.execute(stmt)).scalars().all()
        if not expired_users: return
        log.info("plans.expired_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan("Expired")
        user_ids_to_deactivate = [user.id for user in expired_users]
        notifications_to_add = [Notification(user_id=user.id, message=f"Срок действия тарифа '{user.plan}' истек.", level="error") for user in expired_users]
        session.add_all(notifications_to_add)
        await session.execute(update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False))
        await session.execute(update(User).where(User.id.in_(user_ids_to_deactivate)).values(
            plan="Expired",
            daily_likes_limit=expired_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=expired_plan_limits["daily_add_friends_limit"]
        ))
        await session.commit()

async def _update_friend_request_statuses_async():
    # ... (логика без изменений)
    async with AsyncSessionFactory() as session:
        stmt = select(User).where(User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending))
        users_with_pending = (await session.execute(stmt)).scalars().unique().all()
        if not users_with_pending: return
        log.info("conversion_tracker.start", users_count=len(users_with_pending))
        for user in users_with_pending:
            try:
                vk_token = decrypt_data(user.encrypted_vk_token)
                if not vk_token: continue
                vk_api = VKAPI(access_token=vk_token)
                pending_reqs = (await session.execute(select(FriendRequestLog).where(
                    FriendRequestLog.user_id == user.id, FriendRequestLog.status == FriendRequestStatus.pending
                ))).scalars().all()
                friends_response = await vk_api.get_user_friends(user_id=user.vk_id)
                if friends_response is None: continue
                friend_ids = {f['id'] for f in friends_response}
                accepted_req_ids = [req.id for req in pending_reqs if req.target_vk_id in friend_ids]
                if accepted_req_ids:
                    await session.execute(update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                        status=FriendRequestStatus.accepted, resolved_at=datetime.datetime.now(pytz.utc)
                    ))
                    log.info("conversion_tracker.updated", user_id=user.id, count=len(accepted_req_ids))
            except VKAuthError: log.warn("conversion_tracker.auth_error", user_id=user.id)
            except Exception as e: log.error("conversion_tracker.user_error", user_id=user.id, error=str(e))
        await session.commit()

async def _generate_all_heatmaps_async():
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        stmt = select(User).where(
            User.plan.in_(['Plus', 'PRO', 'Agency']),
            or_(User.plan_expires_at.is_(None), User.plan_expires_at > now)
        )
        users = (await session.execute(stmt)).scalars().all()
        if not users:
            log.info("heatmap_generator.no_active_users")
            return

        log.info("heatmap_generator.start", users_count=len(users))
        for user in users:
            try:
                # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
                emitter = SystemLogEmitter(task_name="heatmap_generator", user_id=user.id)
                service = AnalyticsService(db=session, user=user, emitter=emitter)
                # -------------------------
                await service.generate_post_activity_heatmap()
            except Exception as e:
                log.error("heatmap_generator.user_error", user_id=user.id, error=str(e))
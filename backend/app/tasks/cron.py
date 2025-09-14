# --- backend/app/tasks/cron.py ---
import asyncio
import datetime
import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, Automation, TaskHistory, User, Notification, FriendRequestLog, FriendRequestStatus
)
from app.services.vk_api import VKAPI, VKAuthError
from app.core.security import decrypt_data
from app.tasks.runner import (
    like_feed, add_recommended_friends, accept_friend_requests, 
    remove_friends_by_criteria, view_stories, eternal_online,
    birthday_congratulation, leave_groups_by_criteria
)
from app.services.analytics_service import AnalyticsService
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG
from app.core.plans import get_limits_for_plan
from app.tasks.utils import run_async_from_sync
import pytz

log = structlog.get_logger(__name__)

TASK_FUNC_MAP = {
    "like_feed": like_feed,
    "add_recommended": add_recommended_friends,
    "birthday_congratulation": birthday_congratulation,
    "accept_friends": accept_friend_requests,
    "remove_friends": remove_friends_by_criteria,
    "view_stories": view_stories,
    "eternal_online": eternal_online,
    "leave_groups": leave_groups_by_criteria,
}

async def _create_and_run_task(session, user_id, task_name, settings):
    task_func = TASK_FUNC_MAP.get(task_name)
    if not task_func:
        log.warn("cron.task_not_found", task_name=task_name)
        return
    
    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_name), None)
    display_name = task_config.name if task_config else "Неизвестная задача"

    task_kwargs = settings.copy() if settings else {}
    if 'task_history_id' in task_kwargs:
        del task_kwargs['task_history_id']

    task_history = TaskHistory(user_id=user_id, task_name=display_name, status="PENDING", parameters=task_kwargs)
    session.add(task_history)
    await session.flush()

    queue_name = 'low_priority' if task_name in ['eternal_online'] else 'default'

    task_result = task_func.apply_async(
        kwargs={'task_history_id': task_history.id, **task_kwargs},
        queue=queue_name
    )
    task_history.celery_task_id = task_result.id

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
    redis_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=2, decode_responses=True)
    lock_key = f"lock:task:run_automations:{automation_group}"
    
    if not await redis_client.set(lock_key, "1", ex=240, nx=True):
        log.warn("run_daily_automations.already_running", group=automation_group)
        await redis_client.close()
        return
    
    try:
        async with AsyncSessionFactory() as session:
            now_utc = datetime.datetime.utcnow()
            moscow_tz = pytz.timezone("Europe/Moscow")
            now_moscow = now_utc.astimezone(moscow_tz)

            automation_ids_in_group = [item.id for item in AUTOMATIONS_CONFIG if item.group == automation_group]

            if not automation_ids_in_group:
                log.warn("run_daily_automations.unknown_group", group=automation_group)
                return

            available_plans = [
                plan_name for plan_name, config in PLAN_CONFIG.items()
                if config.get("available_features") == "*" or any(auto_id in config.get("available_features", []) for auto_id in automation_ids_in_group)
            ]

            stmt = (
                select(Automation)
                .join(User)
                .where(
                    Automation.is_active == True,
                    Automation.automation_type.in_(automation_ids_in_group),
                    User.plan.in_(available_plans),
                    or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
                )
                .options(selectinload(Automation.user))
            )

            result = await session.execute(stmt)
            active_automations = result.scalars().unique().all()

            if not active_automations:
                return

            log.info("run_daily_automations.start", count=len(active_automations), group=automation_group)
            
            for automation in active_automations:
                if automation.automation_type == "eternal_online":
                    settings = automation.settings or {}
                    if settings.get("schedule_type") == "custom":
                        days_of_week = settings.get("days_of_week", [])
                        start_time_str = settings.get("start_time")
                        end_time_str = settings.get("end_time")
                        
                        if now_moscow.weekday() not in days_of_week:
                            continue
                        
                        if start_time_str and end_time_str:
                            try:
                                start_time = datetime.datetime.strptime(start_time_str, "%H:%M").time()
                                end_time = datetime.datetime.strptime(end_time_str, "%H:%M").time()
                                
                                if start_time <= end_time:
                                    if not (start_time <= now_moscow.time() <= end_time):
                                        continue
                                else:
                                    if not (now_moscow.time() >= start_time or now_moscow.time() <= end_time):
                                        continue
                            except ValueError:
                                log.warn("run_daily_automations.invalid_time_format", user_id=automation.user_id)
                                continue
                
                automation.last_run_at = now_utc
                await _create_and_run_task(session, user_id=automation.user_id, task_name=automation.automation_type, settings=automation.settings)
            
            await session.commit()
    finally:
        await redis_client.delete(lock_key)
        await redis_client.close()

async def _check_expired_plans_async():
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        stmt = select(User).where(
            User.plan != 'Expired',
            User.plan_expires_at != None,
            User.plan_expires_at < now
        )
        result = await session.execute(stmt)
        expired_users = result.scalars().all()

        if not expired_users:
            return

        log.info("plans.expired_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan("Expired")
        user_ids_to_deactivate = [user.id for user in expired_users]

        notifications_to_add = [
            Notification(user_id=user.id, message=f"Срок действия тарифа '{user.plan}' истек. Все автоматизации остановлены.", level="error")
            for user in expired_users
        ]
        session.add_all(notifications_to_add)

        deactivate_automations_stmt = update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False)
        await session.execute(deactivate_automations_stmt)

        deactivate_users_stmt = update(User).where(User.id.in_(user_ids_to_deactivate)).values(
            plan="Expired",
            daily_likes_limit=expired_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=expired_plan_limits["daily_add_friends_limit"]
        )
        await session.execute(deactivate_users_stmt)
        
        await session.commit()
        log.info("plans.expired_processed_and_deactivated", count=len(user_ids_to_deactivate))

async def _update_friend_request_statuses_async():
    async with AsyncSessionFactory() as session:
        stmt = select(User).where(User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending))
        users_with_pending = (await session.execute(stmt)).scalars().unique().all()
        
        if not users_with_pending:
            return
            
        log.info("conversion_tracker.start", users_count=len(users_with_pending))
        
        for user in users_with_pending:
            try:
                vk_token = decrypt_data(user.encrypted_vk_token)
                if not vk_token: continue
                
                vk_api = VKAPI(access_token=vk_token)
                
                pending_reqs_stmt = select(FriendRequestLog).where(
                    FriendRequestLog.user_id == user.id,
                    FriendRequestLog.status == FriendRequestStatus.pending
                )
                pending_reqs = (await session.execute(pending_reqs_stmt)).scalars().all()
                
                friends_response = await vk_api.get_user_friends(user_id=user.vk_id)
                if friends_response is None: continue
                
                friend_ids = set(friends_response)
                
                accepted_req_ids = [req.id for req in pending_reqs if req.target_vk_id in friend_ids]
                
                if accepted_req_ids:
                    update_stmt = update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                        status=FriendRequestStatus.accepted,
                        resolved_at=datetime.datetime.utcnow()
                    )
                    await session.execute(update_stmt)
                    log.info("conversion_tracker.updated", user_id=user.id, count=len(accepted_req_ids))
            
            except VKAuthError:
                log.warn("conversion_tracker.auth_error", user_id=user.id)
            except Exception as e:
                log.error("conversion_tracker.user_error", user_id=user.id, error=str(e))

        await session.commit()

async def _generate_all_heatmaps_async():
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        # Выбираем активных пользователей с платными тарифами
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
                service = AnalyticsService(db=session, user=user, emitter=None)
                await service.generate_post_activity_heatmap()
            except Exception as e:
                log.error("heatmap_generator.user_error", user_id=user.id, error=str(e))

@celery_app.task(name="app.tasks.cron.generate_all_heatmaps")
def generate_all_heatmaps():
    run_async_from_sync(_generate_all_heatmaps_async())

@celery_app.task(name="app.tasks.cron.aggregate_daily_stats")
def aggregate_daily_stats():
    run_async_from_sync(_aggregate_daily_stats_async())

@celery_app.task(name="app.tasks.cron.run_daily_automations", ignore_result=True)
def run_daily_automations(automation_group: str):
    run_async_from_sync(_run_daily_automations_async(automation_group))

@celery_app.task(name="app.tasks.cron.check_expired_plans")
def check_expired_plans():
    run_async_from_sync(_check_expired_plans_async())

@celery_app.task(name="app.tasks.cron.update_friend_request_statuses")
def update_friend_request_statuses():
    run_async_from_sync(_update_friend_request_statuses_async())
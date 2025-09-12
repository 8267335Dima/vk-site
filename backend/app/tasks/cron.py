# backend/app/tasks/cron.py
import asyncio
import datetime
import structlog
from celery import shared_task
from sqlalchemy import func, select, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, Automation, TaskHistory, User, Notification
)
from app.tasks.runner import (
    like_feed, add_recommended_friends, accept_friend_requests, 
    remove_friends_by_criteria, view_stories, like_friends_feed, eternal_online,
    birthday_congratulation
)
from app.core.config_loader import PLAN_CONFIG
from app.core.plans import get_limits_for_plan
from app.services.analytics_service import AnalyticsService
from app.services.vk_api import VKAuthError
from app.tasks.utils import run_async_from_sync  # <--- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ

log = structlog.get_logger(__name__)
redis_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=2, decode_responses=True)

TASK_FUNC_MAP = {
    "like_feed": like_feed,
    "add_recommended": add_recommended_friends,
    "birthday_congratulation": birthday_congratulation,
    "accept_friends": accept_friend_requests,
    "remove_friends": remove_friends_by_criteria,
    "view_stories": view_stories,
    "like_friends_feed": like_friends_feed,
    "eternal_online": eternal_online,
}

# --- АСИНХРОННЫЕ ХЕЛПЕРЫ И ЛОГИКА (без изменений) ---

async def _create_and_run_task(session, user_id, task_name, settings):
    """(Асинхронный хелпер) Создает TaskHistory и запускает Celery задачу."""
    task_func = TASK_FUNC_MAP.get(task_name)
    if not task_func:
        log.warn("cron.task_not_found", task_name=task_name)
        return

    task_kwargs = settings.copy() if settings else {}
    if 'task_history_id' in task_kwargs:
        del task_kwargs['task_history_id']

    task_history = TaskHistory(user_id=user_id, task_name=task_name, status="PENDING", parameters=task_kwargs)
    session.add(task_history)
    await session.flush()

    queue_name = 'low_priority' if task_name in ['eternal_online'] else 'default'

    task_result = task_func.apply_async(
        kwargs={'task_history_id': task_history.id, **task_kwargs},
        queue=queue_name
    )
    task_history.celery_task_id = task_result.id

async def _aggregate_daily_stats_async():
    """Асинхронная логика: Агрегирует дневную статистику в недельную и месячную."""
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
    """Асинхронная логика: Находит и запускает активные автоматизации."""
    lock_key = f"lock:task:run_automations:{automation_group}"
    if not await redis_client.set(lock_key, "1", ex=240, nx=True):
        log.warn("run_daily_automations.already_running", group=automation_group)
        return
    
    try:
        async with AsyncSessionFactory() as session:
            now = datetime.datetime.utcnow()

            automation_ids_in_group = []
            if automation_group == 'standard':
                automation_ids_in_group = ["like_feed", "add_recommended", "accept_friends", "remove_friends", "like_friends_feed", "view_stories", "birthday_congratulation"]
            elif automation_group == 'online':
                automation_ids_in_group = ["eternal_online"]

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
                    or_(User.plan_expires_at.is_(None), User.plan_expires_at > now)
                )
                # --- ИСПРАВЛЕНИЕ: Правильное использование selectinload ---
                .options(selectinload(Automation.user))
            )

            result = await session.execute(stmt)
            active_automations = result.scalars().unique().all()

            if not active_automations:
                return

            log.info("run_daily_automations.start", count=len(active_automations), group=automation_group)
            
            for automation in active_automations:
                automation.last_run_at = now
                await _create_and_run_task(session, user_id=automation.user_id, task_name=automation.automation_type, settings=automation.settings)
            
            await session.commit()
    finally:
        await redis_client.delete(lock_key)

async def _check_expired_plans_async():
    """Асинхронная логика: Находит пользователей с истекшим тарифом и деактивирует их."""
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        stmt = select(User).where(User.plan_expires_at != None, User.plan_expires_at < now, User.daily_likes_limit > 0)
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
            daily_likes_limit=expired_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=expired_plan_limits["daily_add_friends_limit"]
        )
        await session.execute(deactivate_users_stmt)
        
        await session.commit()
        log.info("plans.expired_processed_and_deactivated", count=len(user_ids_to_deactivate))

async def _snapshot_all_users_friends_count_async():
    """Асинхронная логика: Собирает данные о количестве друзей для всех активных пользователей."""
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        stmt = select(User).where(or_(User.plan_expires_at.is_(None), User.plan_expires_at > now))
        result = await session.execute(stmt)
        active_users = result.scalars().all()

        if not active_users:
            log.info("snapshot_friends.no_active_users")
            return

        log.info("snapshot_friends.start", count=len(active_users))
        processed_count = 0
        for user in active_users:
            async with AsyncSessionFactory() as user_session:
                try:
                    service = AnalyticsService(db=user_session, user=user, emitter=None)
                    await service.snapshot_friends_count()
                    processed_count += 1
                except VKAuthError:
                    log.warn("snapshot_friends.auth_error", user_id=user.id)
                except Exception as e:
                    log.error("snapshot_friends.user_error", user_id=user.id, error=str(e))
        
        log.info("snapshot_friends.success", processed=processed_count)

# --- СИНХРОННЫЕ ЗАДАЧИ-ОБЕРТКИ ДЛЯ CELERY (ИСПРАВЛЕНО) ---

@shared_task(name="app.tasks.cron.aggregate_daily_stats")
def aggregate_daily_stats():
    """Синхронная входная точка для Celery."""
    run_async_from_sync(_aggregate_daily_stats_async())

@shared_task(name="app.tasks.cron.run_daily_automations", ignore_result=True)
def run_daily_automations(automation_group: str):
    """Синхронная входная точка для Celery."""
    run_async_from_sync(_run_daily_automations_async(automation_group))

@shared_task(name="app.tasks.cron.check_expired_plans")
def check_expired_plans():
    """Синхронная входная точка для Celery."""
    run_async_from_sync(_check_expired_plans_async())

@shared_task(name="app.tasks.cron.snapshot_all_users_friends_count")
def snapshot_all_users_friends_count():
    """Синхронная входная точка для Celery."""
    run_async_from_sync(_snapshot_all_users_friends_count_async())
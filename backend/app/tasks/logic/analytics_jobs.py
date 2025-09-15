# --- backend/app/tasks/logic/analytics_jobs.py ---
import datetime
import structlog
import pytz
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionFactory
from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, User, FriendRequestLog, FriendRequestStatus,
    ProfileMetric
)
from app.services.event_emitter import SystemLogEmitter
from app.services.vk_api import VKAPI, VKAuthError
from app.core.security import decrypt_data
from app.services.analytics_service import AnalyticsService
from app.services.profile_analytics_service import ProfileAnalyticsService

log = structlog.get_logger(__name__)

async def _aggregate_daily_stats_async():
    """Агрегирует вчерашнюю дневную статистику в недельную и месячную."""
    async with AsyncSessionFactory() as session:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        
        stmt = select(
            DailyStats.user_id,
            func.sum(DailyStats.likes_count).label("likes"),
            func.sum(DailyStats.friends_added_count).label("friends"),
            func.sum(DailyStats.friend_requests_accepted_count).label("accepted")
        ).where(DailyStats.date == yesterday).group_by(DailyStats.user_id)
        
        daily_sums = (await session.execute(stmt)).all()
        if not daily_sums:
            return

        week_id, month_id = yesterday.strftime('%Y-%W'), yesterday.strftime('%Y-%m')

        for stat_type, identifier in [(WeeklyStats, week_id), (MonthlyStats, month_id)]:
            values = [
                {"user_id": r.user_id, f"{stat_type.__tablename__[:-1]}_identifier": identifier, "likes_count": r.likes,
                 "friends_added_count": r.friends, "friend_requests_accepted_count": r.accepted} for r in daily_sums
            ]
            if not values: continue

            insert_stmt = insert(stat_type).values(values)
            update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['user_id', f"{stat_type.__tablename__[:-1]}_identifier"],
                set_={
                    'likes_count': getattr(stat_type, 'likes_count') + insert_stmt.excluded.likes_count,
                    'friends_added_count': getattr(stat_type, 'friends_added_count') + insert_stmt.excluded.friends_added_count,
                    'friend_requests_accepted_count': getattr(stat_type, 'friend_requests_accepted_count') + insert_stmt.excluded.friend_requests_accepted_count
                }
            )
            await session.execute(update_stmt)
        
        await session.commit()
        log.info("analytics.aggregated_daily_stats", count=len(daily_sums), date=yesterday.isoformat())

async def _snapshot_all_users_metrics_async():
    """Создает снимок ключевых метрик профиля (лайки, друзья) для всех активных пользователей."""
    async with AsyncSessionFactory() as session:
        active_users = (await session.execute(select(User).where(User.plan_expires_at > datetime.datetime.now(datetime.UTC)))).scalars().all()
        if not active_users: return

        log.info("analytics.snapshot_metrics_started", count=len(active_users))
        for user in active_users:
            try:
                # Используем новую сессию для каждого пользователя, чтобы избежать проблем с транзакциями
                async with AsyncSessionFactory() as user_session:
                    service = ProfileAnalyticsService(db=user_session, user=user, emitter=SystemLogEmitter("snapshot_metrics"))
                    await service.snapshot_profile_metrics()
            except VKAuthError:
                log.warn("analytics.snapshot_metrics_auth_error", user_id=user.id)
            except Exception as e:
                log.error("analytics.snapshot_metrics_user_error", user_id=user.id, error=str(e))

async def _generate_all_heatmaps_async():
    """Генерирует тепловые карты активности для всех пользователей с доступом к фиче."""
    async with AsyncSessionFactory() as session:
        users = (await session.execute(select(User).where(User.plan.in_(['Plus', 'PRO', 'Agency'])))).scalars().all()
        if not users: return
        
        log.info("analytics.heatmap_generation_started", count=len(users))
        for user in users:
            try:
                async with AsyncSessionFactory() as user_session:
                    emitter = SystemLogEmitter(task_name="heatmap_generator", user_id=user.id)
                    service = AnalyticsService(db=user_session, user=user, emitter=emitter)
                    await service.generate_post_activity_heatmap()
            except Exception as e:
                log.error("analytics.heatmap_generation_user_error", user_id=user.id, error=str(e))

async def _update_friend_request_statuses_async():
    """Проверяет статусы отправленных заявок в друзья (приняты или нет)."""
    async with AsyncSessionFactory() as session:
        users = (await session.execute(select(User).options(selectinload(User.friend_requests)).where(User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending)))).scalars().unique().all()
        if not users: return

        log.info("analytics.conversion_tracker_started", count=len(users))
        for user in users:
            pending_reqs = [req for req in user.friend_requests if req.status == FriendRequestStatus.pending]
            if not pending_reqs: continue

            try:
                vk_api = VKAPI(access_token=decrypt_data(user.encrypted_vk_token))
                friend_ids = {f['id'] for f in (await vk_api.get_user_friends(user.vk_id))}
                
                accepted_req_ids = [req.id for req in pending_reqs if req.target_vk_id in friend_ids]
                if accepted_req_ids:
                    await session.execute(update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                        status=FriendRequestStatus.accepted, resolved_at=datetime.datetime.now(pytz.utc)
                    ))
                    await session.commit()
                    log.info("analytics.conversion_tracker_updated", user_id=user.id, count=len(accepted_req_ids))
            except VKAuthError:
                log.warn("analytics.conversion_tracker_auth_error", user_id=user.id)
            except Exception as e:
                log.error("analytics.conversion_tracker_user_error", user_id=user.id, error=str(e))
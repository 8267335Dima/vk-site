import datetime
import pytz
import structlog
from collections import Counter

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, User, FriendRequestLog,
    FriendRequestStatus, ProfileMetric, UserActivity, ActionEffectivenessReport,
    TaskHistory
)
from app.services.vk_api import VKAPI, VKAuthError
from app.core.security import decrypt_data
from app.services.analytics_service import AnalyticsService
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.services.event_emitter import SystemLogEmitter

log = structlog.get_logger(__name__)

async def _aggregate_daily_stats_async(session: AsyncSession):
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
        values_to_upsert = []
        id_key = 'week_identifier' if stat_type is WeeklyStats else 'month_identifier'
        for r in daily_sums:
            values_to_upsert.append({
                "user_id": r.user_id,
                id_key: identifier,
                "likes_count": r.likes,
                "friends_added_count": r.friends,
                "friend_requests_accepted_count": r.accepted
            })

        if not values_to_upsert:
            continue
        
        insert_stmt = insert(stat_type).values(values_to_upsert)
        update_dict = {
            'likes_count': getattr(stat_type, 'likes_count') + insert_stmt.excluded.likes_count,
            'friends_added_count': getattr(stat_type, 'friends_added_count') + insert_stmt.excluded.friends_added_count,
            'friend_requests_accepted_count': getattr(stat_type, 'friend_requests_accepted_count') + insert_stmt.excluded.friend_requests_accepted_count
        }
        
        final_stmt = insert_stmt.on_conflict_do_update(
            index_elements=['user_id', id_key],
            set_=update_dict
        )
        await session.execute(final_stmt)

async def _snapshot_all_users_metrics_async(session: AsyncSession):
    now = datetime.datetime.now(pytz.utc)
    stmt = select(User).where(
        (User.plan_expires_at == None) | (User.plan_expires_at > now)
    )
    result = await session.execute(stmt)
    active_users = result.scalars().all()

    if not active_users:
        log.info("snapshot_metrics_task.no_active_users")
        return

    log.info("snapshot_metrics_task.start", count=len(active_users))

    for user in active_users:
        try:
            async with session.begin_nested():
                service = ProfileAnalyticsService(db=session, user=user, emitter=SystemLogEmitter("snapshot_metrics"))
                await service.snapshot_profile_metrics()
        except VKAuthError:
            log.warn("snapshot_metrics_task.auth_error", user_id=user.id)
        except Exception as e:
            log.error("snapshot_metrics_task.user_error", user_id=user.id, error=str(e), exc_info=True)

async def _generate_all_heatmaps_async(session: AsyncSession):
    users_result = await session.execute(select(User).where(User.plan.in_(['PLUS', 'PRO', 'AGENCY'])))
    users = users_result.scalars().all()
    if not users: return
    
    log.info("analytics.heatmap_generation_started", count=len(users))
    for user in users:
        try:
            async with session.begin_nested():
                emitter = SystemLogEmitter(task_name="heatmap_generator")
                emitter.set_context(user_id=user.id)
                service = AnalyticsService(db=session, user=user, emitter=emitter)
                await service.generate_post_activity_heatmap()
        except Exception as e:
            log.error("analytics.heatmap_generation_user_error", user_id=user.id, error=str(e))

async def _update_friend_request_statuses_async(session: AsyncSession):
    stmt = select(User).options(selectinload(User.friend_requests)).where(
        User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending)
    )
    users_with_pending_reqs_result = await session.execute(stmt)
    users_with_pending_reqs = users_with_pending_reqs_result.scalars().unique().all()
    
    if not users_with_pending_reqs:
        return

    for user in users_with_pending_reqs:
        pending_reqs = [req for req in user.friend_requests if req.status == FriendRequestStatus.pending]
        if not pending_reqs:
            continue

        vk_api = None
        try:
            vk_token = decrypt_data(user.encrypted_vk_token)
            if not vk_token:
                continue

            vk_api = VKAPI(access_token=vk_token)
            target_ids = [str(req.target_vk_id) for req in pending_reqs]
            friend_statuses = await vk_api.friends.areFriends(user_ids=",".join(target_ids))
            
            if not friend_statuses:
                continue

            accepted_req_ids = [
                req.id for req, status_info in zip(pending_reqs, friend_statuses)
                if status_info.get("friend_status") == 3
            ]
            
            if accepted_req_ids:
                update_stmt = update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                    status=FriendRequestStatus.accepted, 
                    resolved_at=datetime.datetime.now(pytz.utc)
                )
                await session.execute(update_stmt)

        except Exception as e:
            log.error("analytics.conversion_tracker_user_error", user_id=user.id, error=str(e))
        finally:
            if vk_api:
                await vk_api.close()

async def _process_user_notifications_async(session: AsyncSession):
    users_result = await session.execute(select(User))
    users = users_result.scalars().all()
    if not users:
        return

    for user in users:
        vk_api = None
        try:
            vk_token = decrypt_data(user.encrypted_vk_token)
            if not vk_token: continue
            
            vk_api = VKAPI(access_token=vk_token)
            notifications_response = await vk_api.notifications.get(count=100)
            
            if not notifications_response or not notifications_response.get('items'):
                continue
            
            items = notifications_response.get('items', [])
            like_counter, comment_counter, accepted_friend_requests = Counter(), Counter(), []

            for item in items:
                event_type, feedback = item.get('type'), item.get('feedback')
                if not event_type or not feedback: continue

                source_ids = []
                if isinstance(feedback, list):
                    source_ids = [fb.get('from_id') for fb in feedback if fb.get('from_id', 0) > 0]
                elif isinstance(feedback, dict) and feedback.get('from_id', 0) > 0:
                    source_ids = [feedback.get('from_id')]

                for from_id in source_ids:
                    if 'like_' in event_type:
                        like_counter[from_id] += 1
                    elif 'comment_' in event_type or 'reply_' in event_type:
                        comment_counter[from_id] += 1
                    elif event_type == 'friend_accepted':
                        accepted_friend_requests.append(from_id)

            async with session.begin_nested():
                if like_counter:
                    await _upsert_activity(session, user.id, 'like', like_counter)
                if comment_counter:
                    await _upsert_activity(session, user.id, 'comment', comment_counter)
                if accepted_friend_requests:
                    stmt = update(FriendRequestLog).where(
                        FriendRequestLog.user_id == user.id,
                        FriendRequestLog.target_vk_id.in_(accepted_friend_requests),
                        FriendRequestLog.status == FriendRequestStatus.pending
                    ).values(status=FriendRequestStatus.accepted, resolved_at=datetime.datetime.now(pytz.utc))
                    await session.execute(stmt)
            
            await vk_api.notifications.markAsViewed()
        except Exception as e:
            log.error("analytics.notifications_processor.user_error", user_id=user.id, error=str(e), exc_info=True)
        finally:
            if vk_api:
                await vk_api.close()

async def _upsert_activity(session: AsyncSession, user_id: int, activity_type: str, counter: Counter):
    if not counter: return
    values = [{"user_id": user_id, "source_vk_id": vk_id, "activity_type": activity_type, "count": count} for vk_id, count in counter.items()]
    stmt = insert(UserActivity).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=['user_id', 'source_vk_id', 'activity_type'],
        set_={'count': UserActivity.count + stmt.excluded.count}
    )
    await session.execute(stmt)

async def _generate_effectiveness_report_async(session: AsyncSession, task_history_id: int):
    task_history = await session.get(TaskHistory, task_history_id, options=[selectinload(TaskHistory.user)])
    if not task_history or task_history.task_name != "Добавление друзей":
        return

    user = task_history.user
    start_time = task_history.started_at
    end_time = task_history.finished_at + datetime.timedelta(days=3)

    accepted_reqs_stmt = select(func.count(FriendRequestLog.id)).where(
        FriendRequestLog.user_id == user.id,
        FriendRequestLog.status == FriendRequestStatus.accepted,
        FriendRequestLog.created_at >= start_time,
        FriendRequestLog.resolved_at.between(start_time, end_time)
    )
    accepted_count = (await session.execute(accepted_reqs_stmt)).scalar_one()

    metric_before_stmt = select(ProfileMetric).where(ProfileMetric.user_id == user.id, ProfileMetric.date <= start_time.date()).order_by(ProfileMetric.date.desc()).limit(1)
    metric_after_stmt = select(ProfileMetric).where(ProfileMetric.user_id == user.id, ProfileMetric.date >= end_time.date()).order_by(ProfileMetric.date.asc()).limit(1)
    metric_before = (await session.execute(metric_before_stmt)).scalar_one_or_none()
    metric_after = (await session.execute(metric_after_stmt)).scalar_one_or_none()
    
    followers_growth = (metric_after.followers_count - metric_before.followers_count) if metric_before and metric_after else 0

    report = ActionEffectivenessReport(
        user_id=user.id, task_history_id=task_history.id, task_name=task_history.task_name,
        accepted_friends_count=accepted_count,
        followers_growth=followers_growth,
        task_started_at=start_time, task_finished_at=task_history.finished_at
    )
    session.add(report)
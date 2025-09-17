# --- START OF FILE backend/app/tasks/logic/analytics_jobs.py ---

import datetime
import structlog
import pytz
from contextlib import asynccontextmanager
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
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

@asynccontextmanager
async def get_session(provided_session: AsyncSession | None = None):
    """
    Контекстный менеджер для получения сессии БД.
    Если сессия передана извне (как в тестах), использует ее.
    Иначе, создает новую сессию (как в production).
    """
    if provided_session:
        yield provided_session
    else:
        async with AsyncSessionFactory() as session:
            yield session

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
            values_to_upsert = []
            for r in daily_sums:
                values_to_upsert.append({
                    "user_id": r.user_id,
                    f"{stat_type.__tablename__.replace('s', '')}_identifier": identifier,
                    "likes_count": r.likes,
                    "friends_added_count": r.friends,
                    "friend_requests_accepted_count": r.accepted
                })

            if not values_to_upsert:
                continue
            
            # В SQLAlchemy 2.0+ on_conflict_do_update строится немного иначе
            from sqlalchemy.dialects.postgresql import insert
            
            insert_stmt = insert(stat_type).values(values_to_upsert)
            
            # Определяем, как обновлять поля при конфликте
            update_dict = {
                'likes_count': getattr(stat_type, 'likes_count') + insert_stmt.excluded.likes_count,
                'friends_added_count': getattr(stat_type, 'friends_added_count') + insert_stmt.excluded.friends_added_count,
                'friend_requests_accepted_count': getattr(stat_type, 'friend_requests_accepted_count') + insert_stmt.excluded.friend_requests_accepted_count
            }
            
            # Собираем окончательный запрос
            final_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['user_id', f"{stat_type.__tablename__.replace('s', '')}_identifier"],
                set_=update_dict
            )
            await session.execute(final_stmt)
        
        await session.commit()
        log.info("analytics.aggregated_daily_stats", count=len(daily_sums), date=yesterday.isoformat())

async def _snapshot_all_users_metrics_async(session_for_test: AsyncSession | None = None):
    """Создает снимок ключевых метрик профиля для всех активных пользователей."""
    async with get_session(session_for_test) as session:
        now = datetime.datetime.now(datetime.UTC)
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
                    # Создаем сервис с той же сессией
                    service = ProfileAnalyticsService(db=session, user=user, emitter=SystemLogEmitter("snapshot_metrics"))
                    await service.snapshot_profile_metrics()
                # begin_nested() автоматически коммитит, если не было ошибок
            except VKAuthError:
                log.warn("snapshot_metrics_task.auth_error", user_id=user.id)
                # Роллбэк для этого пользователя произойдет автоматически при выходе из блока `begin_nested`
            except Exception as e:
                log.error("snapshot_metrics_task.user_error", user_id=user.id, error=str(e), exc_info=True)

        if not session_for_test:
            await session.commit()

        log.info("snapshot_metrics_task.finished")


async def _generate_all_heatmaps_async():
    """Генерирует тепловые карты активности для всех пользователей с доступом к фиче."""
    async with AsyncSessionFactory() as session:
        users = (await session.execute(select(User).where(User.plan.in_(['PLUS', 'PRO', 'AGENCY'])))).scalars().all()
        if not users: return
        
        log.info("analytics.heatmap_generation_started", count=len(users))
        for user in users:
            try:
                async with AsyncSessionFactory() as user_session:
                    async with user_session.begin():
                        emitter = SystemLogEmitter(task_name="heatmap_generator")
                        emitter.set_context(user_id=user.id)
                        service = AnalyticsService(db=user_session, user=user, emitter=emitter)
                        await service.generate_post_activity_heatmap()
            except Exception as e:
                log.error("analytics.heatmap_generation_user_error", user_id=user.id, error=str(e))

async def _update_friend_request_statuses_async():
    """Проверяет статусы отправленных заявок в друзья (приняты или нет)."""
    async with AsyncSessionFactory() as session:
        # Находим пользователей, у которых есть заявки в статусе 'pending'
        stmt = select(User).options(selectinload(User.friend_requests)).where(
            User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending)
        )
        users_with_pending_reqs = (await session.execute(stmt)).scalars().unique().all()
        
        if not users_with_pending_reqs:
            return

        log.info("analytics.conversion_tracker_started", count=len(users_with_pending_reqs))
        
        for user in users_with_pending_reqs:
            pending_reqs = [req for req in user.friend_requests if req.status == FriendRequestStatus.pending]
            if not pending_reqs:
                continue

            vk_api = None
            try:
                vk_token = decrypt_data(user.encrypted_vk_token)
                if not vk_token:
                    log.warn("analytics.conversion_tracker_no_token", user_id=user.id)
                    continue

                vk_api = VKAPI(access_token=vk_token)
                
                # Получаем актуальный список ID друзей
                friends_response = await vk_api.get_user_friends(user_id=user.vk_id, fields="")
                if not friends_response or 'items' not in friends_response:
                    continue
                
                friend_ids = set(friends_response['items'])
                
                accepted_req_ids = [req.id for req in pending_reqs if req.target_vk_id in friend_ids]
                
                if accepted_req_ids:
                    update_stmt = update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                        status=FriendRequestStatus.accepted, 
                        resolved_at=datetime.datetime.now(pytz.utc)
                    )
                    await session.execute(update_stmt)
                    await session.commit()
                    log.info("analytics.conversion_tracker_updated", user_id=user.id, count=len(accepted_req_ids))

            except VKAuthError:
                log.warn("analytics.conversion_tracker_auth_error", user_id=user.id)
            except Exception as e:
                log.error("analytics.conversion_tracker_user_error", user_id=user.id, error=str(e))
            finally:
                if vk_api:
                    await vk_api.close()


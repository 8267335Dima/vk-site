# backend/app/tasks/profile_parser_jobs.py
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionFactory
from app.db.models import User
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.services.event_emitter import SystemLogEmitter
from app.services.vk_api import VKAuthError

log = structlog.get_logger(__name__)

async def snapshot_single_user_metrics_task(ctx, user_id: int):
    """
    ARQ-задача для сбора метрик ОДНОГО пользователя.
    """
    async with AsyncSessionFactory() as session:
        try:
            user = await session.get(User, user_id)
            if not user or user.is_deleted:
                return

            emitter = SystemLogEmitter("snapshot_metrics")
            emitter.set_context(user.id)
            
            # Используем вложенную транзакцию, чтобы ошибка у одного пользователя
            # не откатила коммиты для других.
            async with session.begin_nested():
                service = ProfileAnalyticsService(db=session, user=user, emitter=emitter)
                await service.snapshot_profile_metrics()
            
            # Основной коммит для этой задачи
            await session.commit()

        except VKAuthError:
            log.warn("snapshot_single_user.auth_error", user_id=user_id)
        except Exception as e:
            log.error("snapshot_single_user.error", user_id=user_id, error=str(e))
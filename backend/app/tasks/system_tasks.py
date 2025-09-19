# backend/app/tasks/system_tasks.py

import structlog
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
from sqlalchemy.orm import selectinload

from app.db.models import ScheduledPost, ScheduledPostStatus
from app.db.session import AsyncSessionFactory
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.services.scenario_service import ScenarioExecutionService
from app.services.event_emitter import RedisEventEmitter

log = structlog.get_logger(__name__)


@asynccontextmanager
async def get_task_db_session(provided_session: Session | None = None):
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


async def publish_scheduled_post_task(ctx, post_id: int, db_session_for_test: Session | None = None):
    """
    ARQ-задача для публикации отложенного поста.
    Может принимать существующую сессию БД для целей тестирования.
    """
    async with get_task_db_session(db_session_for_test) as session:
        post = await session.get(ScheduledPost, post_id, options=[selectinload(ScheduledPost.user)])
        
        if not post or post.status != ScheduledPostStatus.scheduled:
            if not post:
                log.warn("publish_post.not_found", post_id=post_id)
            return

        user = post.user
        emitter = RedisEventEmitter(ctx['redis_pool'])
        emitter.set_context(user.id)

        if not user:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Пользователь не найден"
            if not db_session_for_test:
                await session.commit()
            return

        vk_token = decrypt_data(user.encrypted_vk_token)
        if not vk_token:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Токен пользователя недействителен"
            await emitter.send_system_notification(session, "Не удалось опубликовать пост: токен VK недействителен.", "error")
            if not db_session_for_test:
                await session.commit()
            return

        vk_api = VKAPI(access_token=vk_token)
        try:
            attachments_str = ",".join(post.attachments or [])
            result = await vk_api.wall.post(
                owner_id=int(post.vk_profile_id),
                message=post.post_text or "",
                attachments=attachments_str
            )
            if result and result.get("post_id"):
                post.status = ScheduledPostStatus.published
                post.vk_post_id = str(result.get("post_id"))
                await emitter.send_system_notification(session, "Запланированный пост успешно опубликован.", "success")
            else:
                 raise VKAPIError(f"Не удалось опубликовать пост. Ответ VK: {result}", 0)

        except (VKAPIError, Exception) as e:
            error_message = str(e.message) if isinstance(e, VKAPIError) else str(e)
            post.status = ScheduledPostStatus.failed
            post.error_message = error_message
            log.error("post_scheduler.failed", post_id=post.id, user_id=user.id, error=error_message)
            await emitter.send_system_notification(session, f"Ошибка публикации поста: {error_message}", "error")
        finally:
            await vk_api.close()

        if db_session_for_test:
            await session.flush()
        else:
            await session.commit()


async def run_scenario_from_scheduler_task(ctx, scenario_id: int, user_id: int, db_session_for_test: Session | None = None):
    """
    ARQ-задача для запуска сценария по расписанию.
    Может принимать существующую сессию БД для целей тестирования.
    """
    log.info("scenario.runner.start", scenario_id=scenario_id, user_id=user_id)
    try:
        async with get_task_db_session(db_session_for_test) as session:
            executor = ScenarioExecutionService(session, scenario_id, user_id)
            await executor.run()
    except Exception as e:
        log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e), exc_info=True)
    finally:
        log.info("scenario.runner.finished", scenario_id=scenario_id)
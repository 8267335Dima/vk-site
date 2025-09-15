import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import ScheduledPost, ScheduledPostStatus
from app.db.session import AsyncSessionFactory
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.services.scenario_service import ScenarioExecutionService
from app.services.event_emitter import RedisEventEmitter

log = structlog.get_logger(__name__)

async def publish_scheduled_post_task(ctx, post_id: int):
    async with AsyncSessionFactory() as session:
        post = await session.get(ScheduledPost, post_id, options=[selectinload(ScheduledPost.user)])
        if not post or post.status != ScheduledPostStatus.scheduled:
            return

        user = post.user
        emitter = RedisEventEmitter(ctx['redis_pool'])
        emitter.set_context(user.id)

        if not user:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Пользователь не найден"
            await session.commit()
            return

        vk_token = decrypt_data(user.encrypted_vk_token)
        if not vk_token:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Токен пользователя недействителен"
            await emitter.send_system_notification(session, "Не удалось опубликовать пост: токен VK недействителен.", "error")
            await session.commit()
            return

        vk_api = VKAPI(access_token=vk_token)
        try:
            result = await vk_api.wall.post(
                owner_id=int(post.vk_profile_id),
                message=post.post_text or "",
                attachments=",".join(post.attachments or [])
            )
            post.status = ScheduledPostStatus.published
            post.vk_post_id = str(result.get("post_id"))
            await emitter.send_system_notification(session, "Запланированный пост успешно опубликован.", "success")
        except (VKAPIError, Exception) as e:
            error_message = str(e.message) if isinstance(e, VKAPIError) else str(e)
            post.status = ScheduledPostStatus.failed
            post.error_message = error_message
            log.error("post_scheduler.failed", post_id=post.id, user_id=user.id, error=error_message)
            await emitter.send_system_notification(session, f"Ошибка публикации поста: {error_message}", "error")

        await session.commit()

async def run_scenario_from_scheduler_task(ctx, scenario_id: int, user_id: int):
    log.info("scenario.runner.start", scenario_id=scenario_id, user_id=user_id)
    try:
        async with AsyncSessionFactory() as session:
            executor = ScenarioExecutionService(session, scenario_id, user_id)
            await executor.run()
    except Exception as e:
        log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e), exc_info=True)
    finally:
        log.info("scenario.runner.finished", scenario_id=scenario_id)
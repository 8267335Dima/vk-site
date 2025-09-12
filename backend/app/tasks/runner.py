from app.celery_app import celery_app
from celery import Task
from redis.asyncio import Redis as AsyncRedis
import asyncio
from sqlalchemy.future import select
import random
from sqlalchemy.orm import selectinload
from app.db.models import Scenario, User, TaskHistory
from app.services.event_emitter import RedisEventEmitter
from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService
from app.core.config import settings
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAuthError, VKRateLimitError, VKAPIError
from app.tasks.base_task import AppBaseTask, AsyncSessionFactory_Celery
import structlog
# --- ИЗМЕНЕНИЕ: Исправлен неверный путь импорта ---
from app.tasks.utils import run_async_from_sync
from app.services.humanizer import Humanizer

log = structlog.get_logger(__name__)

TASK_SERVICE_MAP = {
    "like_feed": (FeedService, "like_newsfeed"),
    "like_friends_feed": (FeedService, "like_friends_feed"),
    "add_recommended": (OutgoingRequestService, "add_recommended_friends"),
    "accept_friends": (IncomingRequestService, "accept_friend_requests"),
    "remove_friends": (FriendManagementService, "remove_friends_by_criteria"),
    "view_stories": (StoryService, "view_stories"),
    "birthday_congratulation": (AutomationService, "congratulate_friends_with_birthday"),
    "mass_messaging": (MessageService, "send_mass_message"),
    "eternal_online": (AutomationService, "set_online_status"),
    "leave_groups": (GroupManagementService, "leave_groups_by_criteria"),
}

async def _execute_task_logic(task_history_id: int, task_name_key: str, **kwargs):
    redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)
    emitter = RedisEventEmitter(redis_client)
    
    try:
        async with AsyncSessionFactory_Celery() as session:
            task_history = await session.get(TaskHistory, task_history_id)
            if not task_history:
                log.error("task_runner.history_not_found", id=task_history_id)
                return

            user = await session.get(User, task_history.user_id)
            if not user:
                raise RuntimeError(f"User {task_history.user_id} not found")
                
            emitter.set_context(user.id, task_history.id)
            task_history.status = "STARTED"
            await session.commit()
            await emitter.send_task_status_update(status="STARTED", task_name=task_history.task_name, created_at=task_history.created_at)

            try:
                ServiceClass, method_name = TASK_SERVICE_MAP[task_name_key]
                service_instance = ServiceClass(db=session, user=user, emitter=emitter)
                await getattr(service_instance, method_name)(**kwargs)

            except (VKRateLimitError, VKAPIError) as e:
                await emitter.send_task_status_update(status="RETRY", result=f"Ошибка VK API: {e.message}", task_name=task_history.task_name, created_at=task_history.created_at)
                raise e
            
            except (VKAuthError, UserActionException) as e:
                await emitter.send_system_notification(session, str(e), "error")
                raise e
            
            except Exception as e:
                log.exception("task_runner.unhandled_exception", id=task_history_id, error=str(e))
                await emitter.send_system_notification(session, f"Произошла внутренняя ошибка: {e}", "error")
                raise
    finally:
        await redis_client.close()

# --- ИЗМЕНЕНИЕ: Добавлена новая задача ---
def _create_task(name, **kwargs):
    @celery_app.task(name=f"app.tasks.runner.{name}", bind=True, base=AppBaseTask, **kwargs)
    def task_wrapper(self: Task, task_history_id: int, **task_kwargs):
        return run_async_from_sync(_execute_task_logic(task_history_id, name, **task_kwargs))
    return task_wrapper

like_feed = _create_task("like_feed", max_retries=3, default_retry_delay=300)
add_recommended_friends = _create_task("add_recommended", max_retries=3, default_retry_delay=300)
accept_friend_requests = _create_task("accept_friends", max_retries=3, default_retry_delay=60)
remove_friends_by_criteria = _create_task("remove_friends", max_retries=2, default_retry_delay=60)
view_stories = _create_task("view_stories", max_retries=2, default_retry_delay=60)
birthday_congratulation = _create_task("birthday_congratulation", max_retries=2, default_retry_delay=120)
mass_messaging = _create_task("mass_messaging", max_retries=2, default_retry_delay=300)
eternal_online = _create_task("eternal_online", max_retries=5, default_retry_delay=60)
like_friends_feed = _create_task("like_friends_feed", max_retries=3, default_retry_delay=300)
leave_groups_by_criteria = _create_task("leave_groups", max_retries=2, default_retry_delay=60)


@celery_app.task(bind=True, base=AppBaseTask, name="app.tasks.runner.run_scenario_from_scheduler")
def run_scenario_from_scheduler(self: Task, scenario_id: int, user_id: int):
    async def _run_scenario_logic():
        redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
        lock_key = f"lock:scenario:user:{user_id}"
        
        if not await redis_client.set(lock_key, "1", ex=3600, nx=True):
            log.warn("scenario.runner.already_running", scenario_id=scenario_id, user_id=user_id)
            await redis_client.close()
            return

        log.info("scenario.runner.start", scenario_id=scenario_id)
        try:
            async with AsyncSessionFactory_Celery() as session:
                stmt = select(Scenario).where(Scenario.id == scenario_id).options(selectinload(Scenario.steps), selectinload(Scenario.user))
                scenario = (await session.execute(stmt)).scalar_one_or_none()
                
                if not scenario or not scenario.is_active:
                    log.warn("scenario.runner.not_found_or_inactive", scenario_id=scenario_id)
                    return

                emitter = RedisEventEmitter(redis_client)
                emitter.set_context(user_id=user_id)
                humanizer = Humanizer(delay_profile=scenario.user.delay_profile, logger_func=emitter.send_log)

                sorted_steps = sorted(scenario.steps, key=lambda s: s.step_order)

                for step in sorted_steps:
                    ServiceClass, method_name = TASK_SERVICE_MAP[step.action_type]
                    service_instance = ServiceClass(db=session, user=scenario.user, emitter=emitter)
                    
                    batch_settings = step.batch_settings or {}
                    parts = batch_settings.get("parts", 1)
                    total_count = step.settings.get("count", 0)

                    if parts > 1 and total_count > 0:
                        count_per_part = total_count // parts
                        for i in range(parts):
                            current_kwargs = step.settings.copy()
                            current_kwargs['count'] = count_per_part
                            if i == parts - 1:
                                current_kwargs['count'] += total_count % parts

                            log.info("scenario.step.batch_execution", scenario_id=scenario_id, step=step.action_type, batch=f"{i+1}/{parts}")
                            await getattr(service_instance, method_name)(**current_kwargs)
                            
                            if i < parts - 1:
                                await humanizer._sleep(60, 180, f"Пауза между частями шага ({i+1}/{parts})")
                    else:
                        await getattr(service_instance, method_name)(**step.settings)
        except Exception as e:
            log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e))
        finally:
            await redis_client.delete(lock_key)
            await redis_client.close()
            log.info("scenario.runner.finished", scenario_id=scenario_id)
    
    return run_async_from_sync(_run_scenario_logic())
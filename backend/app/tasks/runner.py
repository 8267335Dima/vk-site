# backend/app/tasks/runner.py
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
from app.core.config import settings
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAuthError, VKRateLimitError, VKAPIError
from app.tasks.base_task import AppBaseTask, AsyncSessionFactory_Celery
import structlog

log = structlog.get_logger(__name__)
redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)

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
}

async def _execute_task_logic(task_history_id: int, task_name_key: str, **kwargs):
    emitter = RedisEventEmitter(redis_client)
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

@celery_app.task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300)
def like_feed(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "like_feed", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300)
def add_recommended_friends(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "add_recommended", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=60)
def accept_friend_requests(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "accept_friends", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=60)
def remove_friends_by_criteria(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "remove_friends", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=60)
def view_stories(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "view_stories", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=120)
def birthday_congratulation(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "birthday_congratulation", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=300)
def mass_messaging(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "mass_messaging", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=5, default_retry_delay=60)
def eternal_online(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "eternal_online", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300)
def like_friends_feed(self: Task, task_history_id: int, **kwargs):
    return self._run_async_from_sync(_execute_task_logic(task_history_id, "like_friends_feed", **kwargs))

@celery_app.task(bind=True, base=AppBaseTask, name="app.tasks.runner.run_scenario_from_scheduler")
def run_scenario_from_scheduler(self: Task, scenario_id: int):
    async def _run_scenario_logic():
        log.info("scenario.runner.start", scenario_id=scenario_id)
        async with AsyncSessionFactory_Celery() as session:
            try:
                stmt = select(Scenario).where(Scenario.id == scenario_id).options(selectinload(Scenario.steps))
                result = await session.execute(stmt)
                scenario = result.scalar_one_or_none()
                if not scenario or not scenario.is_active:
                    log.warn("scenario.runner.not_found_or_inactive", scenario_id=scenario_id)
                    return
                sorted_steps = sorted(scenario.steps, key=lambda s: s.step_order)
                for step in sorted_steps:
                    pass
            except Exception as e:
                log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e))
                raise
        log.info("scenario.runner.finished", scenario_id=scenario_id)
    
    return self._run_async_from_sync(_run_scenario_logic())
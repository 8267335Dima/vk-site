# backend/app/tasks/runner.py
from celery import shared_task, Task
from redis.asyncio import Redis as AsyncRedis

from app.db.models import User, TaskHistory
from app.services.event_emitter import RedisEventEmitter
from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService # НОВЫЙ
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
    "mass_messaging": (MessageService, "send_mass_message"), # НОВЫЙ
    "eternal_online": (AutomationService, "set_online_status"), # НОВЫЙ
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
        await emitter.send_task_status_update(status="STARTED")

        try:
            ServiceClass, method_name = TASK_SERVICE_MAP[task_name_key]
            service_instance = ServiceClass(db=session, user=user, emitter=emitter)
            await getattr(service_instance, method_name)(**kwargs)

        except (VKRateLimitError, VKAPIError) as e:
            await emitter.send_task_status_update(status="RETRY", result=f"Ошибка VK API: {e.message}")
            raise e
        
        except (VKAuthError, UserActionException) as e:
            await emitter.send_system_notification(session, str(e), "error")
            raise e
        
        except Exception as e:
            log.exception("task_runner.unhandled_exception", id=task_history_id, error=str(e))
            await emitter.send_system_notification(session, f"Произошла внутренняя ошибка: {e}", "error")
            raise

# --- Определения задач Celery ---

@shared_task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300)
async def like_feed(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "like_feed", **kwargs)

# ... (аналогичные декораторы для всех задач из TASK_SERVICE_MAP)
@shared_task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300)
async def add_recommended_friends(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "add_recommended", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=60)
async def accept_friend_requests(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "accept_friends", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=60)
async def remove_friends_by_criteria(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "remove_friends", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=60)
async def view_stories(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "view_stories", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=120)
async def birthday_congratulation(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "birthday_congratulation", **kwargs)

# НОВЫЕ ЗАДАЧИ
@shared_task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=300)
async def mass_messaging(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "mass_messaging", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=5, default_retry_delay=60)
async def eternal_online(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "eternal_online", **kwargs)
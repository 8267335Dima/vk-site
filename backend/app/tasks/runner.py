# backend/app/tasks/runner.py
from app.celery_app import celery_app
from celery import Task
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.lock import Lock
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db.models import Scenario, User, TaskHistory, ScheduledPost, ScheduledPostStatus, Automation
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
from app.services.vk_api import VKAPI, VKAuthError, VKRateLimitError, VKAPIError
from app.core.constants import TaskKey
from app.db.session import AsyncSessionFactory
import structlog
from app.tasks.utils import run_async_from_sync
from app.services.scenario_service import ScenarioExecutionService
from app.api.schemas import actions as ActionSchemas
from app.core.security import decrypt_data

log = structlog.get_logger(__name__)

# Карта соответствия ключа задачи, сервиса и Pydantic-модели для параметров
TASK_CONFIG_MAP = {
    TaskKey.LIKE_FEED: (FeedService, "like_newsfeed", ActionSchemas.LikeFeedRequest),
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "add_recommended_friends", ActionSchemas.AddFriendsRequest),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "accept_friend_requests", ActionSchemas.AcceptFriendsRequest),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "remove_friends_by_criteria", ActionSchemas.RemoveFriendsRequest),
    TaskKey.VIEW_STORIES: (StoryService, "view_stories", ActionSchemas.EmptyRequest),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "congratulate_friends_with_birthday", ActionSchemas.BirthdayCongratulationRequest),
    TaskKey.MASS_MESSAGING: (MessageService, "send_mass_message", ActionSchemas.MassMessagingRequest),
    TaskKey.ETERNAL_ONLINE: (AutomationService, "set_online_status", ActionSchemas.EmptyRequest),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "leave_groups_by_criteria", ActionSchemas.LeaveGroupsRequest),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "join_groups_by_criteria", ActionSchemas.JoinGroupsRequest),
}

class BaseTaskWithContext(Task):
    acks_late = True
    
    def __init__(self):
        self.session = None; self.redis = None; self.emitter = None
        self.user = None; self.task_history = None

    async def _setup_context(self, task_history_id):
        self.session = AsyncSessionFactory()
        self.redis = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)
        self.emitter = RedisEventEmitter(self.redis)
        
        stmt = select(TaskHistory).where(TaskHistory.id == task_history_id).options(
            selectinload(TaskHistory.user).selectinload(User.proxies)
        )
        self.task_history = (await self.session.execute(stmt)).scalar_one_or_none()

        if not self.task_history: return False
        self.user = self.task_history.user
        if not self.user: return False
            
        self.emitter.set_context(self.user.id, self.task_history.id)
        return True

    async def _teardown_context(self):
        if self.redis: await self.redis.close()
        if self.session: await self.session.close()

    async def _run_task(self, task_history_id: int, task_name_key: str, **kwargs):
        if not await self._setup_context(task_history_id): return
        
        try:
            ServiceClass, method_name, ParamsModel = TASK_CONFIG_MAP[TaskKey(task_name_key)]
            
            try:
                # Валидация параметров через Pydantic-модель
                params = ParamsModel(**kwargs)
            except Exception as e:
                raise UserActionException(f"Неверные параметры для задачи: {e}")

            self.task_history.status = "STARTED"
            await self.session.commit()
            await self.emitter.send_task_status_update(status="STARTED", task_name=self.task_history.task_name, created_at=self.task_history.created_at)

            service_instance = ServiceClass(db=self.session, user=self.user, emitter=self.emitter)
            
            # В сервисы теперь передается строго типизированный Pydantic-объект
            await getattr(service_instance, method_name)(params)
            
            self.task_history.status = "SUCCESS"
            self.task_history.result = "Задача успешно выполнена."

        except VKAuthError as e:
            redis_lock_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2")
            auth_error_key = f"auth_error_count:{self.user.id}"
            error_count = await redis_lock_client.incr(auth_error_key)
            await redis_lock_client.expire(auth_error_key, 3600)
            
            if error_count >= 3:
                log.error("task_runner.auth_error_persistent", user_id=self.user.id, error=str(e))
                await self.emitter.send_system_notification(self.session, "Критическая ошибка авторизации VK. Ваш токен недействителен. Все автоматизации остановлены. Пожалуйста, войдите в систему заново.", "error")
                await self.session.execute(update(Automation).where(Automation.user_id == self.user.id).values(is_active=False))
            else:
                 log.warn("task_runner.auth_error_transient", user_id=self.user.id, error=str(e), attempt=error_count)
                 await self.emitter.send_system_notification(self.session, "Произошла ошибка авторизации VK. Если ошибка повторится, автоматизации будут остановлены.", "warning")

            await redis_lock_client.close()
            raise e 

        except (VKRateLimitError, VKAPIError) as e:
            retry_delay = 60 * (self.request.retries + 1)
            log.warn("task_runner.api_error_retrying", id=task_history_id, error=str(e), next_try_in_sec=retry_delay)
            self.task_history.status = "RETRY"
            self.task_history.result = f"Ошибка VK API, повтор через {retry_delay // 60} мин: {e.message}"
            raise self.retry(exc=e, countdown=retry_delay)
        
        except UserActionException as e:
            await self.emitter.send_system_notification(self.session, str(e), "error")
            raise e
        
        except Exception as e:
            log.exception("task_runner.unhandled_exception", id=task_history_id, error=str(e))
            await self.emitter.send_system_notification(self.session, f"Произошла внутренняя ошибка при выполнении задачи '{self.task_history.task_name}'.", "error")
            raise
        
        finally:
            if self.task_history and self.session: await self.session.commit()
            await self._teardown_context()

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        async def _async_on_failure():
            task_history_id = kwargs.get('task_history_id')
            if not await self._setup_context(task_history_id): return
            
            self.task_history.status = "FAILURE"
            self.task_history.result = f"Задача провалена: {exc!r}"
            await self.session.commit()
            await self.emitter.send_task_status_update(status="FAILURE", result=self.task_history.result, task_name=self.task_history.task_name, created_at=self.task_history.created_at)
            await self._teardown_context()
        
        run_async_from_sync(_async_on_failure())

    def on_success(self, retval, task_id, args, kwargs):
        async def _async_on_success():
            task_history_id = kwargs.get('task_history_id')
            if not await self._setup_context(task_history_id): return
            
            await self.emitter.send_task_status_update(status="SUCCESS", result=self.task_history.result, task_name=self.task_history.task_name, created_at=self.task_history.created_at)
            await self._teardown_context()
        
        run_async_from_sync(_async_on_success())
        
    def __call__(self, *args, **kwargs):
        return run_async_from_sync(self.run(*args, **kwargs))

def _create_task(name: TaskKey, **celery_options):
    task_config = {
        'max_retries': 3, 'default_retry_delay': 300,
        'soft_time_limit': 900, 'time_limit': 1200,
        **celery_options
    }
    
    @celery_app.task(name=f"app.tasks.runner.{name.value}", bind=True, base=BaseTaskWithContext, **task_config)
    def task_wrapper(self: BaseTaskWithContext, task_history_id: int, **kwargs):
        return run_async_from_sync(self._run_task(task_history_id, name.value, **kwargs))
    return task_wrapper

# --- Определение всех задач ---
like_feed = _create_task(TaskKey.LIKE_FEED)
add_recommended_friends = _create_task(TaskKey.ADD_RECOMMENDED)
accept_friend_requests = _create_task(TaskKey.ACCEPT_FRIENDS)
remove_friends_by_criteria = _create_task(TaskKey.REMOVE_FRIENDS)
view_stories = _create_task(TaskKey.VIEW_STORIES)
birthday_congratulation = _create_task(TaskKey.BIRTHDAY_CONGRATULATION, soft_time_limit=1800, time_limit=2000)
mass_messaging = _create_task(TaskKey.MASS_MESSAGING, soft_time_limit=3600, time_limit=3800)
eternal_online = _create_task(TaskKey.ETERNAL_ONLINE, max_retries=5, default_retry_delay=60, soft_time_limit=120, time_limit=180)
leave_groups_by_criteria = _create_task(TaskKey.LEAVE_GROUPS)
join_groups_by_criteria = _create_task(TaskKey.JOIN_GROUPS)


@celery_app.task(bind=True, base=BaseTaskWithContext, name="app.tasks.runner.run_scenario_from_scheduler")
def run_scenario_from_scheduler(self: Task, scenario_id: int, user_id: int):
    async def _run_scenario_logic():
        log.info("scenario.runner.start", scenario_id=scenario_id, user_id=user_id)
        redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2")
        lock = Lock(redis_client, f"lock:scenario:{scenario_id}", timeout=3600, blocking=False)
        
        if not await lock.acquire():
            log.warn("scenario.runner.already_running", scenario_id=scenario_id)
            await redis_client.close()
            return

        try:
            async with AsyncSessionFactory() as session:
                executor = ScenarioExecutionService(session, scenario_id, user_id)
                await executor.run()
        except Exception as e:
            log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e), exc_info=True)
        finally:
            await lock.release()
            await redis_client.close()
            log.info("scenario.runner.finished", scenario_id=scenario_id)
    
    return run_async_from_sync(_run_scenario_logic())


@celery_app.task(bind=True, base=BaseTaskWithContext, name="app.tasks.runner.publish_scheduled_post", soft_time_limit=300, time_limit=400)
def publish_scheduled_post(self: Task, post_id: int):
    async def _publish_logic():
        async with AsyncSessionFactory() as session:
            post = await session.get(ScheduledPost, post_id)
            if not post or post.status != ScheduledPostStatus.scheduled:
                return

            user = await session.get(User, post.user_id)
            if not user:
                post.status = ScheduledPostStatus.failed
                post.error_message = "Пользователь не найден"
                await session.commit()
                return

            vk_token = decrypt_data(user.encrypted_vk_token)
            if not vk_token:
                post.status = ScheduledPostStatus.failed
                post.error_message = "Токен пользователя недействителен"
                await session.commit()
                return

            vk_api = VKAPI(access_token=vk_token)

            try:
                result = await vk_api.wall_post(
                    owner_id=post.vk_profile_id,
                    message=post.post_text,
                    attachments=",".join(post.attachments or [])
                )
                post.status = ScheduledPostStatus.published
                post.vk_post_id = str(result.get("post_id"))
            except VKAuthError as e:
                post.status = ScheduledPostStatus.failed
                post.error_message = f"Ошибка авторизации: {e.message}. Обновите токен."
            except Exception as e:
                post.status = ScheduledPostStatus.failed
                post.error_message = str(e)
            
            await session.commit()
    
    return run_async_from_sync(_publish_logic())
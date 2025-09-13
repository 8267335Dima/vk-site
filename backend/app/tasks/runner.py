# backend/app/tasks/runner.py
from app.celery_app import celery_app
from celery import Task
from redis.asyncio import Redis as AsyncRedis
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
from app.core.security import decrypt_data
from app.core.constants import TaskKey
from app.tasks.base_task import AppBaseTask, AsyncSessionFactory_Celery
import structlog
from app.tasks.utils import run_async_from_sync
from app.services.scenario_service import ScenarioExecutionService

log = structlog.get_logger(__name__)

TASK_SERVICE_MAP = {
    TaskKey.LIKE_FEED: (FeedService, "like_newsfeed"),
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "add_recommended_friends"),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "accept_friend_requests"),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "remove_friends_by_criteria"),
    TaskKey.VIEW_STORIES: (StoryService, "view_stories"),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "congratulate_friends_with_birthday"),
    TaskKey.MASS_MESSAGING: (MessageService, "send_mass_message"),
    TaskKey.ETERNAL_ONLINE: (AutomationService, "set_online_status"),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "leave_groups_by_criteria"),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "join_groups_by_criteria"),
}

# --- ИЗМЕНЕНИЕ 1: Добавляем `self: Task` как первый аргумент ---
async def _execute_task_logic(self: Task, task_history_id: int, task_name_key: str, **kwargs):
    redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)
    emitter = RedisEventEmitter(redis_client)
    user = None # Инициализируем user
    task_history = None # Инициализируем task_history
    
    async with AsyncSessionFactory_Celery() as session:
        try:
            task_history_stmt = select(TaskHistory).where(TaskHistory.id == task_history_id).options(
                selectinload(TaskHistory.user).selectinload(User.proxies)
            )
            task_history = (await session.execute(task_history_stmt)).scalar_one_or_none()

            if not task_history:
                log.error("task_runner.history_not_found", id=task_history_id)
                return

            user = task_history.user
            if not user:
                raise RuntimeError(f"User {task_history.user_id} not found")
                
            emitter.set_context(user.id, task_history.id)
            task_history.status = "STARTED"
            await session.commit()
            await emitter.send_task_status_update(status="STARTED", task_name=task_history.task_name, created_at=task_history.created_at)

            ServiceClass, method_name = TASK_SERVICE_MAP[TaskKey(task_name_key)]
            service_instance = ServiceClass(db=session, user=user, emitter=emitter)
            await getattr(service_instance, method_name)(**kwargs)

        except VKAuthError as e:
            if user:
                log.error("task_runner.auth_error", user_id=user.id, error=str(e))
                await emitter.send_system_notification(
                    session, "Ошибка авторизации VK. Ваш токен недействителен. Все автоматизации остановлены. Пожалуйста, войдите в систему заново.", "error"
                )
                deactivate_stmt = update(Automation).where(Automation.user_id == user.id).values(is_active=False)
                await session.execute(deactivate_stmt)
                await session.commit()
            raise e
        
        except (VKRateLimitError, VKAPIError) as e:
            if task_history:
                await emitter.send_task_status_update(status="RETRY", result=f"Ошибка VK API, задача будет повторена: {e.message}", task_name=task_history.task_name, created_at=task_history.created_at)
            # --- ИЗМЕНЕНИЕ 2: Теперь `self` доступен и эта строка корректна ---
            raise self.retry(exc=e)
        
        except UserActionException as e:
            await emitter.send_system_notification(session, str(e), "error")
            raise e
        
        except Exception as e:
            log.exception("task_runner.unhandled_exception", id=task_history_id, error=str(e))
            if task_history:
                await emitter.send_system_notification(session, f"Произошла внутренняя ошибка при выполнении задачи '{task_history.task_name}'.", "error")
            raise
        finally:
            await redis_client.close()

def _create_task(name: TaskKey, **kwargs):
    task_kwargs = {
        'max_retries': 3,
        'default_retry_delay': 300,
        'soft_time_limit': 900,
        'time_limit': 1200,
        **kwargs
    }
    
    @celery_app.task(name=f"app.tasks.runner.{name.value}", bind=True, base=AppBaseTask, **task_kwargs)
    def task_wrapper(self: Task, task_history_id: int, **kwargs):
        # --- ИЗМЕНЕНИЕ 3: Передаем `self` в асинхронную функцию ---
        return run_async_from_sync(_execute_task_logic(self, task_history_id, name.value, **kwargs))
    return task_wrapper

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


@celery_app.task(bind=True, base=AppBaseTask, name="app.tasks.runner.run_scenario_from_scheduler")
def run_scenario_from_scheduler(self: Task, scenario_id: int, user_id: int):
    async def _run_scenario_logic():
        log.info("scenario.runner.start", scenario_id=scenario_id, user_id=user_id)
        redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
        lock_key = f"lock:scenario:{scenario_id}"
        
        if not await redis_client.set(lock_key, "1", ex=3600, nx=True):
            log.warn("scenario.runner.already_running", scenario_id=scenario_id)
            await redis_client.close()
            return

        try:
            async with AsyncSessionFactory_Celery() as session:
                executor = ScenarioExecutionService(session, scenario_id, user_id)
                await executor.run()
        except Exception as e:
            log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e), exc_info=True)
        finally:
            await redis_client.delete(lock_key)
            await redis_client.close()
            log.info("scenario.runner.finished", scenario_id=scenario_id)
    
    return run_async_from_sync(_run_scenario_logic())


@celery_app.task(bind=True, base=AppBaseTask, name="app.tasks.runner.publish_scheduled_post", soft_time_limit=300, time_limit=400)
def publish_scheduled_post(self: Task, post_id: int):
    async def _publish_logic():
        async with AsyncSessionFactory_Celery() as session:
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
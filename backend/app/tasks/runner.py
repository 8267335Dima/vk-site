# backend/app/tasks/runner.py
from celery import shared_task, Task, chain
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis as AsyncRedis

from app.db.models import User, TaskHistory, Scenario
from app.services.event_emitter import RedisEventEmitter
from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.core.config import settings
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAuthError, VKRateLimitError, VKAPIError
from app.tasks.base_task import AppBaseTask, AsyncSessionFactory_Celery
import structlog

log = structlog.get_logger(__name__)
redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)

# Карта для связи имени задачи с классом сервиса и его методом
TASK_SERVICE_MAP = {
    "like_feed": (FeedService, "like_newsfeed"),
    "like_friends_feed": (FeedService, "like_friends_feed"),
    "add_recommended": (OutgoingRequestService, "add_recommended_friends"),
    "accept_friends": (IncomingRequestService, "accept_friend_requests"),
    "remove_friends": (FriendManagementService, "remove_friends_by_criteria"),
    "view_stories": (StoryService, "view_stories"),
    "birthday_congratulation": (AutomationService, "congratulate_friends_with_birthday"),
}

async def _execute_task_logic(task_history_id: int, task_name_key: str, **kwargs):
    """
    Единая асинхронная логика для выполнения всех пользовательских задач.
    """
    emitter = RedisEventEmitter(redis_client)
    async with AsyncSessionFactory_Celery() as session:
        task_history = await session.get(TaskHistory, task_history_id)
        if not task_history:
            log.error("task_runner.task_history_not_found", task_history_id=task_history_id)
            return

        user = await session.get(User, task_history.user_id)
        if not user:
            raise RuntimeError(f"User {task_history.user_id} not found for task {task_history_id}")
            
        emitter.set_context(user.id, task_history.id)
        task_history.status = "STARTED"
        await session.commit()
        await emitter.send_task_status_update(status="STARTED")

        try:
            ServiceClass, method_name = TASK_SERVICE_MAP.get(task_name_key, (None, None))
            if not ServiceClass or not hasattr(ServiceClass, method_name):
                raise ValueError(f"No service logic found for task name: {task_name_key}")

            service_instance = ServiceClass(db=session, user=user, emitter=emitter)
            service_method = getattr(service_instance, method_name)
            
            await service_method(**kwargs)

        except (VKRateLimitError, VKAPIError) as e:
            await emitter.send_task_status_update(status="RETRY", result=f"Ошибка VK API: {e.message}")
            raise e
        
        except (VKAuthError, UserActionException) as e:
            await emitter.send_system_notification(session, str(e), "error")
            raise e
        
        except Exception as e:
            log.exception("task_runner.unhandled_exception", task_history_id=task_history_id, error=str(e))
            await emitter.send_system_notification(session, f"Произошла внутренняя ошибка: {e}", "error")
            raise

# --- ЗАДАЧИ ---

@shared_task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300, name="app.tasks.runner.like_feed")
async def like_feed(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "like_feed", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300, name="app.tasks.runner.like_friends_feed")
async def like_friends_feed(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "like_friends_feed", **kwargs)
    
@shared_task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=300, name="app.tasks.runner.add_recommended_friends")
async def add_recommended_friends(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "add_recommended", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=3, default_retry_delay=60, name="app.tasks.runner.accept_friend_requests")
async def accept_friend_requests(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "accept_friends", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=60, name="app.tasks.runner.remove_friends_by_criteria")
async def remove_friends_by_criteria(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "remove_friends", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=60, name="app.tasks.runner.view_stories")
async def view_stories(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "view_stories", **kwargs)

@shared_task(bind=True, base=AppBaseTask, max_retries=2, default_retry_delay=120, name="app.tasks.runner.birthday_congratulation")
async def birthday_congratulation(self: Task, task_history_id: int, **kwargs):
    await _execute_task_logic(task_history_id, "birthday_congratulation", **kwargs)


# --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: Возвращаем карту функций Celery для использования в сценариях ---
CELERY_TASK_FUNC_MAP = {
    "like_feed": like_feed,
    "add_recommended": add_recommended_friends,
    "birthday_congratulation": birthday_congratulation,
    "accept_friends": accept_friend_requests,
    "remove_friends": remove_friends_by_criteria,
    "view_stories": view_stories,
    "like_friends_feed": like_friends_feed,
}


# --- Логика сценариев ---

@shared_task(bind=True, base=AppBaseTask, name="app.tasks.runner.execute_scenario_chain_finalizer")
async def execute_scenario_chain_finalizer(self: Task, results, scenario_task_id: int):
    await self._update_task_history_async(scenario_task_id, "SUCCESS", "Сценарий успешно выполнен.")

async def _run_scenario_logic(scenario_task_id: int):
    emitter = RedisEventEmitter(redis_client)
    async with AsyncSessionFactory_Celery() as session:
        task_history = await session.get(TaskHistory, scenario_task_id)
        if not task_history: return
        
        scenario_id = task_history.parameters.get("scenario_id")
        scenario = await session.get(Scenario, scenario_id, options=[selectinload(Scenario.steps)])
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found.")
        
        emitter.set_context(scenario.user_id, scenario_task_id)
        
        step_tasks = []
        for step in scenario.steps:
            # --- ИСПРАВЛЕНИЕ: Используем локальную карту CELERY_TASK_FUNC_MAP ---
            task_func = CELERY_TASK_FUNC_MAP.get(step.action_type)
            if not task_func:
                log.warn("scenario_runner.step_task_not_found", action_type=step.action_type)
                continue
            
            step_history = TaskHistory(
                user_id=scenario.user_id, task_name=f"Шаг сценария: {step.action_type}",
                status="PENDING", parameters=step.settings, celery_task_id=task_history.celery_task_id
            )
            session.add(step_history)
            await session.flush()
            
            step_signature = task_func.s(task_history_id=step_history.id, **step.settings)
            step_tasks.append(step_signature)

        await session.commit()

        if not step_tasks:
            await emitter.send_log("В сценарии нет действительных шагов.", "warning")
            await AppBaseTask()._update_task_history_async(scenario_task_id, "SUCCESS", "Сценарий выполнен (нет шагов).")
            return
        
        final_task = execute_scenario_chain_finalizer.s(scenario_task_id=scenario_task_id)
        workflow = chain(step_tasks) | final_task
        workflow.apply_async(queue='default')
        
        await emitter.send_log(f"Сценарий '{scenario.name}' запущен.", "info")

@shared_task(bind=True, base=AppBaseTask, name="app.tasks.runner.run_scenario_from_scheduler")
async def run_scenario_from_scheduler(self: Task, scenario_id: int):
    async with AsyncSessionFactory_Celery() as session:
        scenario = await session.get(Scenario, scenario_id)
        if not scenario or not scenario.is_active: return
        
        task_history = TaskHistory(
            user_id=scenario.user_id, celery_task_id=self.request.id,
            task_name=f"Сценарий: {scenario.name}", status="STARTED",
            parameters={"scenario_id": scenario.id}
        )
        session.add(task_history)
        await session.commit()
        
        await _run_scenario_logic(task_history.id)
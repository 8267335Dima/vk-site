import functools
import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db.models import User, TaskHistory, Automation
from app.db.session import AsyncSessionFactory
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAPIError, VKAuthError
from app.core.constants import TaskKey
from app.tasks.service_maps import TASK_CONFIG_MAP

log = structlog.get_logger(__name__)

def arq_task_runner(func):
    """
    Декоратор, который оборачивает основную логику задачи в стандартный
    обработчик: управление статусами, ошибками, эмиттером и сессией.
    """
    @functools.wraps(func)
    async def wrapper(ctx, task_history_id: int, **kwargs):
        async with AsyncSessionFactory() as session:
            stmt = select(TaskHistory).where(TaskHistory.id == task_history_id).options(
                selectinload(TaskHistory.user).selectinload(User.proxies)
            )
            task_history = (await session.execute(stmt)).scalar_one_or_none()

            if not task_history or not task_history.user:
                log.error("task.runner.not_found", task_history_id=task_history_id)
                return

            emitter = RedisEventEmitter(ctx['redis_pool'])
            emitter.set_context(task_history.user.id, task_history.id)

            try:
                task_history.status = "STARTED"
                await session.commit()
                await emitter.send_task_status_update(status="STARTED", task_name=task_history.task_name, created_at=task_history.created_at)

                await func(session, task_history.user, task_history.parameters or {}, emitter)

                task_history.status = "SUCCESS"
                task_history.result = "Задача успешно выполнена."

            except VKAuthError:
                task_history.status = "FAILURE"
                task_history.result = "Ошибка авторизации VK. Токен невалиден."
                log.error("task_runner.auth_error_critical", user_id=task_history.user.id)
                await emitter.send_system_notification(session, "Критическая ошибка: токен VK недействителен. Все автоматизации остановлены. Пожалуйста, войдите в систему заново.", "error")
                await session.execute(update(Automation).where(Automation.user_id == task_history.user.id).values(is_active=False))
            
            except UserActionException as e:
                task_history.status = "FAILURE"
                task_history.result = str(e)
                await emitter.send_system_notification(session, str(e), "warning")
            
            except VKAPIError as e:
                task_history.status = "FAILURE"
                task_history.result = f"Ошибка VK API: {e.message}"
                log.error("task_runner.generic_vk_error", user_id=task_history.user.id, error=str(e))
                await emitter.send_system_notification(session, f"Произошла непредвиденная ошибка при обращении к API ВКонтакте: '{e.message}'.", "error")

            except Exception as e:
                task_history.status = "FAILURE"
                task_history.result = f"Внутренняя ошибка сервера: {type(e).__name__}"
                log.exception("task_runner.unhandled_exception", id=task_history_id)
                await emitter.send_system_notification(session, "Произошла внутренняя ошибка сервера при выполнении задачи.", "error")
            
            finally:
                await session.merge(task_history)
                await session.commit()
                await emitter.send_task_status_update(status=task_history.status, result=task_history.result, task_name=task_history.task_name, created_at=task_history.created_at)
    return wrapper

async def _run_service_method(session, user, params, emitter, task_key: TaskKey):
    """Находит нужный сервис и метод по ключу и выполняет его."""
    ServiceClass, method_name, ParamsModel = TASK_CONFIG_MAP[task_key]
    validated_params = ParamsModel(**params)
    service_instance = ServiceClass(db=session, user=user, emitter=emitter)
    await getattr(service_instance, method_name)(validated_params)

@arq_task_runner
async def like_feed_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.LIKE_FEED)

@arq_task_runner
async def add_recommended_friends_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.ADD_RECOMMENDED)

@arq_task_runner
async def accept_friend_requests_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.ACCEPT_FRIENDS)

@arq_task_runner
async def remove_friends_by_criteria_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.REMOVE_FRIENDS)

@arq_task_runner
async def view_stories_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.VIEW_STORIES)

@arq_task_runner
async def birthday_congratulation_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.BIRTHDAY_CONGRATULATION)

@arq_task_runner
async def mass_messaging_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.MASS_MESSAGING)

@arq_task_runner
async def eternal_online_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.ETERNAL_ONLINE)

@arq_task_runner
async def leave_groups_by_criteria_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.LEAVE_GROUPS)

@arq_task_runner
async def join_groups_by_criteria_task(session, user, params, emitter):
    await _run_service_method(session, user, params, emitter, TaskKey.JOIN_GROUPS)
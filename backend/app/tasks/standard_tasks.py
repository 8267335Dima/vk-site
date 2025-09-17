# backend/app/tasks/standard_tasks.py

import functools
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

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
    Декоратор-обертка для всех ARQ задач, выполняемых пользователем.
    (описание без изменений)
    """
    @functools.wraps(func)
    async def wrapper(ctx, task_history_id: int, **kwargs):
        emitter_for_test = kwargs.pop("emitter_for_test", None)

        async with AsyncSessionFactory() as session:
            task_history = None
            emitter = None
            # --- ИСПРАВЛЕНИЕ: Заранее объявляем переменные для хранения данных ---
            # Это защитит нас от доступа к "просроченным" атрибутам после commit.
            task_name = "Неизвестная задача"
            created_at = None
            user_id = None
            
            try:
                # Загружаем все необходимые данные одним запросом ("жадная" загрузка)
                stmt = select(TaskHistory).where(TaskHistory.id == task_history_id).options(
                    joinedload(TaskHistory.user).selectinload(User.proxies)
                )
                task_history = (await session.execute(stmt)).scalar_one_or_none()

                if not task_history or not task_history.user:
                    log.error("task.runner.not_found_final", task_history_id=task_history_id)
                    return

                # --- ИСПРАВЛЕНИЕ: Считываем все нужные данные в локальные переменные ДО первого commit ---
                task_name = task_history.task_name
                created_at = task_history.created_at
                user_id = task_history.user.id

                emitter = emitter_for_test or RedisEventEmitter(ctx['redis_pool'])
                emitter.set_context(user_id, task_history_id)
                
                # Обновляем статус и делаем commit
                task_history.status = "STARTED"
                await session.commit()
                # !!! С ЭТОГО МОМЕНТА ОБЪЕКТ task_history "ПРОСРОЧЕН" !!!
                
                # Теперь этот вызов абсолютно безопасен, так как мы используем локальные переменные
                await emitter.send_task_status_update(status="STARTED", task_name=task_name, created_at=created_at)

                # Вызываем основную логику задачи, передавая "просроченные" объекты.
                # Функция func сама будет работать внутри этой же сессии и SQLAlchemy корректно
                # подгрузит нужные данные для них.
                summary_result = await func(session, task_history.user, task_history.parameters or {}, emitter)

                task_history.status = "SUCCESS"
                task_history.result = summary_result if isinstance(summary_result, str) else "Задача успешно выполнена."

            except (UserActionException, VKAPIError, VKAuthError) as e:
                if task_history:
                    await session.rollback()
                    task_history.status = "FAILURE"
                    if isinstance(e, VKAuthError):
                        task_history.result = "Ошибка авторизации VK. Токен невалиден."
                        log.error("task_runner.auth_error_critical", user_id=user_id)
                        if emitter: await emitter.send_system_notification(session, f"Критическая ошибка: токен VK недействителен для задачи '{task_name}'. Автоматизации остановлены.", "error")
                        await session.execute(update(Automation).where(Automation.user_id == user_id).values(is_active=False))
                    else:
                        error_message = str(getattr(e, 'message', e))
                        task_history.result = f"Ошибка: {error_message}"
                        if emitter: await emitter.send_system_notification(session, f"Задача '{task_name}' завершилась с ошибкой: {error_message}", "error")

            except Exception as e:
                if task_history:
                    await session.rollback()
                    task_history.status = "FAILURE"
                    task_history.result = f"Внутренняя ошибка сервера: {type(e).__name__}"
                    log.exception("task_runner.unhandled_exception", id=task_history_id)
                    if emitter: await emitter.send_system_notification(session, f"Задача '{task_name}' завершилась из-за внутренней ошибки сервера.", "error")
            
            finally:
                if task_history:
                    final_status = task_history.status
                    final_result = task_history.result
                    
                    await session.commit()
                    
                    if emitter:
                        # Используем безопасные локальные переменные для финального уведомления
                        await emitter.send_task_status_update(
                            status=final_status,
                            result=final_result,
                            task_name=task_name,
                            created_at=created_at
                        )
    return wrapper


async def _run_service_method(session, user, params, emitter, task_key: TaskKey):
    """Вспомогательная функция: находит нужный сервис и метод по ключу и выполняет его."""
    ServiceClass, method_name, ParamsModel = TASK_CONFIG_MAP[task_key]
    validated_params = ParamsModel(**params)
    service_instance = ServiceClass(db=session, user=user, emitter=emitter)
    return await getattr(service_instance, method_name)(validated_params)


@arq_task_runner
async def like_feed_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.LIKE_FEED)

@arq_task_runner
async def add_recommended_friends_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.ADD_RECOMMENDED)

@arq_task_runner
async def accept_friend_requests_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.ACCEPT_FRIENDS)

@arq_task_runner
async def remove_friends_by_criteria_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.REMOVE_FRIENDS)

@arq_task_runner
async def view_stories_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.VIEW_STORIES)

@arq_task_runner
async def birthday_congratulation_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.BIRTHDAY_CONGRATULATION)

@arq_task_runner
async def mass_messaging_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.MASS_MESSAGING)

@arq_task_runner
async def eternal_online_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.ETERNAL_ONLINE)

@arq_task_runner
async def leave_groups_by_criteria_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.LEAVE_GROUPS)

@arq_task_runner
async def join_groups_by_criteria_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.JOIN_GROUPS)
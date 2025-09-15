# backend/app/tasks/main_tasks.py
import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db.models import User, TaskHistory, ScheduledPost, ScheduledPostStatus, Automation
from app.db.session import AsyncSessionFactory
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAPI, VKAuthError
from app.core.constants import TaskKey
from app.tasks.service_maps import TASK_CONFIG_MAP
from app.core.security import decrypt_data
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.services.scenario_service import ScenarioExecutionService

log = structlog.get_logger(__name__)


async def _execute_task_logic(ctx, task_history_id: int):
    """
    Универсальная функция для выполнения логики любой задачи.
    """
    async with AsyncSessionFactory() as session:
        # Шаг 1: "Жадно" загружаем все, что нам нужно.
        stmt = (
            select(TaskHistory)
            .where(TaskHistory.id == task_history_id)
            .options(
                selectinload(TaskHistory.user).selectinload(User.proxies)
            )
        )
        result = await session.execute(stmt)
        task_history = result.scalar_one_or_none()

        if not task_history or not task_history.user:
            log.error("task.logic.not_found", task_history_id=task_history_id)
            return

        # Шаг 2: Извлекаем все необходимые данные в локальные переменные.
        user_for_task = task_history.user
        current_task_name = task_history.task_name
        current_created_at = task_history.created_at
        task_parameters = task_history.parameters or {}

        # Шаг 3: Отсоединяем объект пользователя от сессии.
        session.expunge(user_for_task)

        redis_pool = ctx['redis_pool']
        emitter = RedisEventEmitter(redis_pool)
        emitter.set_context(user_for_task.id, task_history_id)
        
        try:
            # Шаг 4: Теперь можно безопасно коммитить изменение статуса.
            task_history.status = "STARTED"
            await session.commit()
            
            await emitter.send_task_status_update(status="STARTED", task_name=current_task_name, created_at=current_created_at)

            task_key_str = next((item.id for item in AUTOMATIONS_CONFIG if item.name == current_task_name), None)
            if not task_key_str:
                raise ValueError(f"Не удалось найти ключ задачи для имени '{current_task_name}'")

            ServiceClass, method_name, ParamsModel = TASK_CONFIG_MAP[TaskKey(task_key_str)]
            params = ParamsModel(**task_parameters)

            service_instance = ServiceClass(db=session, user=user_for_task, emitter=emitter)
            await getattr(service_instance, method_name)(params)

            task_history.status = "SUCCESS"
            task_history.result = "Задача успешно выполнена."

        except VKAuthError as e:
            task_history.status = "FAILURE"
            task_history.result = "Ошибка авторизации VK. Токен невалиден."
            log.error("task_runner.auth_error_critical", user_id=user_for_task.id, error=str(e))
            await emitter.send_system_notification(session, "Критическая ошибка: токен VK недействителен. Автоматизации остановлены.", "error")
            await session.execute(update(Automation).where(Automation.user_id == user_for_task.id).values(is_active=False))
        except UserActionException as e:
            task_history.status = "FAILURE"
            task_history.result = str(e)
            await emitter.send_system_notification(session, str(e), "error")
        except Exception as e:
            task_history.status = "FAILURE"
            task_history.result = f"Непредвиденная ошибка: {type(e).__name__}"
            log.exception("task_runner.unhandled_exception", id=task_history_id)
        
        finally:
            final_status = task_history.status
            final_result = task_history.result
            
            await session.merge(task_history)
            await session.commit()
            
            await emitter.send_task_status_update(status=final_status, result=final_result, task_name=current_task_name, created_at=current_created_at)


# --- Определяем все задачи, теперь они принимают `ctx` ---

async def like_feed_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def add_recommended_friends_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def accept_friend_requests_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def remove_friends_by_criteria_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def view_stories_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def birthday_congratulation_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def mass_messaging_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def eternal_online_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def leave_groups_by_criteria_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def join_groups_by_criteria_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)


# --- Задачи со своей собственной логикой ---

async def publish_scheduled_post_task(ctx, post_id: int):
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
            # wall.post не существует в vk_api.py, предполагаем, что это была опечатка и имелся в виду универсальный метод
            # или специальный метод для постов, которого нет в предоставленных файлах.
            # Для исправления используем базовый _make_request.
            result = await vk_api._make_request("wall.post", params={
                "owner_id": int(post.vk_profile_id),
                "message": post.post_text or "",
                "attachments": ",".join(post.attachments or [])
            })
            post.status = ScheduledPostStatus.published
            post.vk_post_id = str(result.get("post_id"))
        except VKAuthError as e:
            post.status = ScheduledPostStatus.failed
            post.error_message = f"Ошибка авторизации: {e.message}. Обновите токен."
        except Exception as e:
            post.status = ScheduledPostStatus.failed
            post.error_message = str(e)

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
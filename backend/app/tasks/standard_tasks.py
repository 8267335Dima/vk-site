import functools
import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from datetime import datetime, UTC
from app.repositories.stats import StatsRepository
from app.api.schemas.users import AllLimitsResponse, LimitStatus
from app.db.models import User, TaskHistory, Automation
from app.db.session import AsyncSessionFactory
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAPIError, VKAuthError
from app.core.enums import TaskKey 
from app.tasks.task_maps import TASK_CONFIG_MAP
from contextlib import asynccontextmanager

log = structlog.get_logger(__name__)

def arq_task_runner(func):
    @functools.wraps(func)
    async def wrapper(ctx, task_history_id: int, **kwargs):
        session_for_test = kwargs.pop("session_for_test", None)
        emitter_for_test = kwargs.pop("emitter_for_test", None)

        @asynccontextmanager
        async def get_session_context():
            if session_for_test:
                yield session_for_test
            else:
                async with AsyncSessionFactory() as session:
                    yield session
        
        async with get_session_context() as session:
            task_history = None
            emitter = None
            user = None
            
            try:
                stmt = select(TaskHistory).where(TaskHistory.id == task_history_id).options(
                    joinedload(TaskHistory.user).selectinload(User.proxies)
                )
                task_history = (await session.execute(stmt)).scalar_one_or_none()

                if not task_history or not task_history.user:
                    log.error("task.runner.not_found_final", task_history_id=task_history_id)
                    return

                user = task_history.user
                emitter = emitter_for_test or RedisEventEmitter(ctx['redis_pool'])
                emitter.set_context(user.id, task_history_id)
                
                task_history.status = "STARTED"
                task_history.started_at = datetime.now(UTC)
                await session.commit()
                await emitter.send_task_status_update(status="STARTED", task_name=task_history.task_name, created_at=task_history.created_at)

                if user.is_shadow_banned:
                    raise UserActionException("Действие отменено (теневой бан).")
                
                task_params = task_history.parameters or {}
                summary_result = await func(session, user, task_params, emitter)
                
                task_history.status = "SUCCESS"
                task_history.result = summary_result if isinstance(summary_result, str) else "Задача успешно выполнена."

            except (UserActionException, VKAPIError, VKAuthError) as e:
                if task_history:
                    await session.rollback()
                    task_history.status = "FAILURE"
                    if isinstance(e, VKAuthError):
                        task_history.result = "Ошибка авторизации VK. Токен невалиден."
                        if emitter: await emitter.send_system_notification(session, f"Критическая ошибка: токен VK недействителен для задачи '{task_history.task_name}'. Автоматизации остановлены.", "error")
                        await session.execute(update(Automation).where(Automation.user_id == user.id).values(is_active=False))
                    else:
                        error_message = str(getattr(e, 'message', e))
                        task_history.result = f"Ошибка: {error_message}"
                        if emitter: await emitter.send_system_notification(session, f"Задача '{task_history.task_name}' завершилась с ошибкой: {error_message}", "error")

            except Exception as e:
                if task_history:
                    await session.rollback()
                    task_history.status = "FAILURE"
                    task_history.result = f"Внутренняя ошибка сервера: {type(e).__name__}"
                    log.exception("task_runner.unhandled_exception", id=task_history_id)
                    if emitter: await emitter.send_system_notification(session, f"Задача '{task_history.task_name}' завершилась из-за внутренней ошибки сервера.", "error")
            
            finally:
                if task_history and user and emitter:
                    task_history.finished_at = datetime.now(UTC)
                    await session.commit()
                    
                    await emitter.send_task_status_update(
                        status=task_history.status,
                        result=task_history.result,
                        task_name=task_history.task_name,
                        created_at=task_history.created_at
                    )
                    
                    stats_repo = StatsRepository(session)
                    today_stats = await stats_repo.get_or_create_today_stats(user.id)
                    all_limits = AllLimitsResponse(
                        likes=LimitStatus(used=today_stats.likes_count, limit=user.daily_likes_limit),
                        add_friends=LimitStatus(used=today_stats.friends_added_count, limit=user.daily_add_friends_limit),
                        messages=LimitStatus(used=today_stats.messages_sent_count, limit=user.daily_message_limit),
                        posts=LimitStatus(used=today_stats.posts_created_count, limit=user.daily_posts_limit),
                        join_groups=LimitStatus(used=today_stats.groups_joined_count, limit=user.daily_join_groups_limit),
                        leave_groups=LimitStatus(used=today_stats.groups_left_count, limit=user.daily_leave_groups_limit),
                    )
                    await emitter.send_stats_update(all_limits.model_dump())

                    if task_history.status == "SUCCESS" and task_history.task_name == "Добавление друзей":
                        await ctx['redis_pool'].enqueue_job(
                            "generate_effectiveness_report_task",
                            task_history_id=task_history.id,
                            _queue_name='low_priority'
                        )
                    
                    await session.commit()
    return wrapper


async def _run_service_method(session, user, params, emitter, task_key: TaskKey):
    ServiceClass, ParamsModel = TASK_CONFIG_MAP[task_key]
    validated_params = ParamsModel(**params)
    service_instance = ServiceClass(db=session, user=user, emitter=emitter)
    return await service_instance.execute(validated_params)


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
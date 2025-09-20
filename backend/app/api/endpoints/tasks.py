# backend/app/api/endpoints/tasks.py

# ОТВЕТСТВЕННОСТЬ: Запуск, предпросмотр и конфигурация новых задач.
from fastapi import APIRouter, Depends, Body, HTTPException, status, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel, ValidationError
from arq.connections import ArqRedis
import datetime

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile, get_arq_pool
from app.db.session import get_db
from app.repositories.stats import StatsRepository
from app.api.schemas.tasks import ActionResponse, PreviewResponse, TaskConfigResponse, TaskField
from app.core.plans import get_plan_config, is_feature_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.enums import TaskKey
from app.services.interfaces import IPreviewableTask
from app.services.vk_api import VKAPIError
from app.tasks.service_maps import TASK_CONFIG_MAP
from app.tasks.task_maps import AnyTaskRequest, TASK_FUNC_MAP, PREVIEW_SERVICE_MAP

router = APIRouter()

# --- Вспомогательная функция (ИСПРАВЛЕНО) ---
async def _enqueue_task(
    user: User, db: AsyncSession, arq_pool: ArqRedis, task_key: str, request_data: BaseModel,
    original_task_name: Optional[str] = None,
    defer_until: Optional[datetime.datetime] = None
) -> TaskHistory:
    """
    Проверяет лимиты и ГОТОВИТ задачу к постановке в очередь.
    НЕ ДЕЛАЕТ COMMIT. Возвращает объект TaskHistory для дальнейшей обработки.
    """
    plan_config = get_plan_config(user.plan)

    max_concurrent = plan_config.get("limits", {}).get("max_concurrent_tasks")
    if max_concurrent is not None:
        active_tasks_query = select(func.count(TaskHistory.id)).where(
            TaskHistory.user_id == user.id,
            TaskHistory.status.in_(["PENDING", "STARTED"])
        )
        active_tasks_count = await db.scalar(active_tasks_query)
        if active_tasks_count >= max_concurrent:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Достигнут лимит на одновременное выполнение задач ({max_concurrent}). Дождитесь завершения текущих."
            )

    if not await is_feature_available_for_plan(user.plan.name_id, task_key, db=db, user=user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Действие недоступно на вашем тарифе '{user.plan}'.")

    task_func_name = TASK_FUNC_MAP.get(TaskKey(task_key))
    if not task_func_name:
        raise HTTPException(status_code=404, detail="Задача не найдена.")

    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key), None)
    task_display_name = original_task_name or (task_config.name if task_config else "Неизвестная задача")

    task_history = TaskHistory(
        user_id=user.id,
        task_name=task_display_name,
        status="PENDING",
        parameters=request_data.model_dump(exclude_unset=True)
    )
    db.add(task_history)
    await db.flush() # Используем flush, чтобы получить ID, но не коммитим
    await db.refresh(task_history)
    
    return task_history

# --- Эндпоинты ---
@router.get("/{task_key}/config", response_model=TaskConfigResponse, summary="Получить конфигурацию UI для задачи")
async def get_task_config(
    task_key: TaskKey,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key.value), None)
    if not task_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конфигурация для задачи не найдена.")

    stats_repo = StatsRepository(db)
    today_stats = await stats_repo.get_or_create_today_stats(current_user.id)
    
    fields = []

    if task_config.has_count_slider:
        limit_map = {
            TaskKey.ADD_RECOMMENDED: ("daily_add_friends_limit", "friends_added_count"),
            TaskKey.LIKE_FEED: ("daily_likes_limit", "likes_count"),
            TaskKey.REMOVE_FRIENDS: ("daily_leave_groups_limit", "friends_removed_count"),
            TaskKey.MASS_MESSAGING: ("daily_message_limit", "messages_sent_count"),
            TaskKey.JOIN_GROUPS: ("daily_join_groups_limit", "groups_joined_count"),
            TaskKey.LEAVE_GROUPS: ("daily_leave_groups_limit", "groups_left_count"),
        }
        
        limit_key, stat_key = limit_map.get(task_key, (None, None))
        
        if limit_key and stat_key:
            total_limit = getattr(current_user, limit_key, 100)
            used_today = getattr(today_stats, stat_key, 0)
            remaining_limit = total_limit - used_today
            max_val = max(0, remaining_limit)
        else:
            max_val = 1000

        fields.append(TaskField(
            name="count",
            type="slider",
            label=task_config.modal_count_label or "Количество",
            default_value=min(task_config.default_count or 20, max_val),
            max_value=max_val
        ))
    return TaskConfigResponse(display_name=task_config.name, has_filters=task_config.has_filters, fields=fields)


@router.post("/run/{task_key}", response_model=ActionResponse, summary="Запустить любую задачу по ее ключу")
async def run_any_task(
    task_key: TaskKey,
    request: Request,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    try:
        raw_body = await request.json()
        
        task_config_tuple = TASK_CONFIG_MAP.get(task_key)
        if not task_config_tuple:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Конфигурация для задачи '{task_key.value}' не найдена.")
        
        RequestModel = task_config_tuple[2]
        request_data = RequestModel(**raw_body)
        
        publish_at_str = raw_body.get("publish_at")
        defer_until = datetime.datetime.fromisoformat(publish_at_str) if publish_at_str else None

    except (ValidationError, TypeError, ValueError) as e:
         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # --- НАЧАЛО ИСПРАВЛЕНИЯ: Единый процесс для всех задач ---
    # 1. Вызываем вспомогательную функцию, которая делает все проверки и готовит объект TaskHistory
    task_history = await _enqueue_task(
        user=current_user,
        db=db,
        arq_pool=arq_pool,
        task_key=task_key.value,
        request_data=request_data,
        defer_until=defer_until
    )
    
    # 2. Готовим параметры для ARQ
    task_func_name = TASK_FUNC_MAP[task_key]
    job_kwargs = {
        'task_history_id': task_history.id,
        **request_data.model_dump()
    }
    if defer_until:
        job_kwargs['_defer_until'] = defer_until
        
    # 3. Ставим задачу в очередь
    job = await arq_pool.enqueue_job(task_func_name, _queue_name='high_priority', **job_kwargs)
    
    # 4. Обновляем ID задачи и коммитим ВСЕ изменения в одной транзакции
    task_history.arq_job_id = job.job_id
    await db.commit()
    
    # 5. Формируем ответ
    message = f"Задача '{task_history.task_name}' успешно добавлена в очередь."
    if defer_until:
        message = f"Задача '{task_history.task_name}' запланирована на {defer_until.strftime('%Y-%m-%d %H:%M:%S')}."
        
    return ActionResponse(message=message, task_id=job.job_id)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---


@router.post("/preview/{task_key}", response_model=PreviewResponse, summary="Предварительный подсчет аудитории для задачи")
async def preview_task_audience(
    task_key: TaskKey,
    request_data: AnyTaskRequest = Body(...),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    if task_key not in TASK_CONFIG_MAP:
        raise HTTPException(status_code=404, detail="Конфигурация для задачи не найдена.")

    ServiceClass, RequestModel = TASK_CONFIG_MAP[task_key]
    
    # Проверяем, что сервис реализует интерфейс для предпросмотра
    if not issubclass(ServiceClass, IPreviewableTask):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Предпросмотр для задачи '{task_key.value}' не поддерживается."
        )

    service_instance = None
    try:
        validated_params = RequestModel(**request_data.model_dump())
        service_instance = ServiceClass(db=db, user=current_user, emitter=None)
        
        targets = await service_instance.get_targets(validated_params)
        return PreviewResponse(found_count=len(targets))
    except VKAPIError as e:
        raise HTTPException(status_code=424, detail=f"Ошибка VK API: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if service_instance and service_instance.vk_api:
            await service_instance.vk_api.close()
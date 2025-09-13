# backend/app/api/endpoints/tasks.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile
from app.db.session import get_db
from app.celery_app import celery_app # <-- НОВЫЙ ИМПОРТ
from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest
)
from app.api.schemas.tasks import ActionResponse, PaginatedTasksResponse
from app.tasks.runner import (
    accept_friend_requests, like_feed, add_recommended_friends,
    view_stories, remove_friends_by_criteria, mass_messaging
)
from app.core.plans import get_plan_config, is_feature_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG

router = APIRouter()

TASK_ENDPOINT_MAP = {
    'accept_friends': (accept_friend_requests, AcceptFriendsRequest, 'filters'),
    'like_feed': (like_feed, LikeFeedRequest, None),
    'add_recommended': (add_recommended_friends, AddFriendsRequest, None),
    'view_stories': (view_stories, EmptyRequest, None),
    'remove_friends': (remove_friends_by_criteria, RemoveFriendsRequest, None),
    'mass_messaging': (mass_messaging, MassMessagingRequest, None),
}

async def _enqueue_task(
    user: User, db: AsyncSession, task_key: str, request_data: BaseModel, original_task_name: Optional[str] = None
):
    """Универсальная функция для постановки задачи в очередь."""
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

    if not is_feature_available_for_plan(user.plan, task_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Действие недоступно на вашем тарифе '{user.plan}'.")

    
    task_func, _, params_key = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not task_func:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    
    task_display_name = original_task_name
    if not task_display_name:
        task_config = next((item for item in AUTOMATIONS_CONFIG if item['id'] == task_key), {})
        task_display_name = task_config.get('name', "Неизвестная задача")

    task_history = TaskHistory(
        user_id=user.id, task_name=task_display_name, status="PENDING",
        parameters=request_data.model_dump(exclude_unset=True)
    )
    db.add(task_history)
    await db.flush()

    celery_kwargs = request_data.model_dump()

    task_result = task_func.apply_async(
        kwargs={'task_history_id': task_history.id, **celery_kwargs},
        queue='high_priority'
    )
    task_history.celery_task_id = task_result.id
    await db.commit()
    
    return ActionResponse(
        message=f"Задача '{task_display_name}' успешно добавлена в очередь.",
        task_id=task_result.id
    )


@router.post("/run/{task_key}", response_model=ActionResponse)
async def run_any_task(
    task_key: str,
    request: dict,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Единый эндпоинт для запуска любой задачи."""
    _, RequestModel, _ = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not RequestModel:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    
    try:
        validated_data = RequestModel(**request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return await _enqueue_task(current_user, db, task_key, validated_data)


@router.get("/history", response_model=PaginatedTasksResponse)
async def get_user_task_history(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None, description="Фильтр по статусу. Если пустой - вернутся все.")
):
    offset = (page - 1) * size
    base_query = select(TaskHistory).where(TaskHistory.user_id == current_user.id)
    
    if status and status.strip():
        base_query = base_query.where(TaskHistory.status == status.upper())
        
    tasks_query = base_query.order_by(TaskHistory.created_at.desc()).offset(offset).limit(size)
    count_query = select(func.count()).select_from(base_query.subquery())
    
    tasks_result = await db.execute(tasks_query)
    total_result = await db.execute(count_query)
    
    tasks = tasks_result.scalars().all()
    total = total_result.scalar_one()
    
    return PaginatedTasksResponse(
        items=tasks, total=total, page=page, size=size,
        has_more=(offset + len(tasks)) < total
    )

@router.post("/{task_history_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(
    task_history_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    """Отменяет задачу, находящуюся в очереди или в процессе выполнения."""
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status not in ["PENDING", "STARTED", "RETRY"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отменить можно только задачи в очереди или в процессе выполнения.")

    if task.celery_task_id:
        celery_app.control.revoke(task.celery_task_id, terminate=True)
    
    task.status = "CANCELLED"
    task.result = "Задача отменена пользователем."
    await db.commit()
    return {"message": "Запрос на отмену задачи отправлен."}

@router.post("/{task_history_id}/retry", response_model=ActionResponse)
async def retry_task(
    task_history_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    """Повторно запускает задачу, которая завершилась с ошибкой."""
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status != "FAILURE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Повторить можно только задачу, завершившуюся с ошибкой.")

    # Пытаемся определить task_key по названию
    task_key = next((item['id'] for item in AUTOMATIONS_CONFIG if item['name'] == task.task_name), None)
    if not task_key:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось определить тип задачи для повторного запуска.")
    
    _, RequestModel, _ = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not RequestModel:
        raise HTTPException(status_code=404, detail="Модель задачи не найдена.")

    validated_data = RequestModel(**(task.parameters or {}))
    
    return await _enqueue_task(current_user, db, task_key, validated_data, original_task_name=task.task_name)
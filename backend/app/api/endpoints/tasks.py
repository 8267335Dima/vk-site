# backend/app/api/endpoints/tasks.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest
)
from app.api.schemas.tasks import ActionResponse, PaginatedTasksResponse
from app.tasks.runner import (
    accept_friend_requests, like_feed, add_recommended_friends,
    view_stories, remove_friends_by_criteria, mass_messaging
)
from app.core.plans import is_feature_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG

router = APIRouter()

# --- ИЗМЕНЕНИЕ: Карта теперь содержит не только функцию, но и ключ для параметров ---
# 'params_key' указывает, какой ключ из Pydantic модели использовать как **kwargs для Celery.
# Если 'params_key' равен None, то вся модель распаковывается.
TASK_ENDPOINT_MAP = {
    'accept_friends': (accept_friend_requests, AcceptFriendsRequest, 'filters'),
    'like_feed': (like_feed, LikeFeedRequest, None),
    'add_recommended': (add_recommended_friends, AddFriendsRequest, None),
    'view_stories': (view_stories, EmptyRequest, None),
    'remove_friends': (remove_friends_by_criteria, RemoveFriendsRequest, None),
    'mass_messaging': (mass_messaging, MassMessagingRequest, None),
}

async def _enqueue_task(
    user: User, db: AsyncSession, task_key: str, request_data: BaseModel
):
    """Универсальная функция для постановки задачи в очередь (УЛУЧШЕННАЯ ВЕРСИЯ)."""
    if not is_feature_available_for_plan(user.plan, task_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Действие недоступно на вашем тарифе '{user.plan}'.")

    task_func, _, params_key = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not task_func:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    
    task_config = next((item for item in AUTOMATIONS_CONFIG if item['id'] == task_key), {})
    task_name = task_config.get('name', "Неизвестная задача")

    task_history = TaskHistory(
        user_id=user.id, task_name=task_name, status="PENDING",
        parameters=request_data.model_dump()
    )
    db.add(task_history)
    await db.flush()

    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЛОГИКИ ---
    celery_kwargs = {}
    model_dict = request_data.model_dump()

    if params_key:
        # Если указан ключ (например, 'filters'), мы берем значение из этого ключа
        # и распаковываем его как аргументы для Celery.
        # Это решает проблему для AcceptFriendsRequest.
        # model_dict['filters'] -> {'sex': 0, ...}
        # celery_kwargs -> {'sex': 0, ...}
        if params_key in model_dict and isinstance(model_dict[params_key], dict):
            celery_kwargs = model_dict[params_key]
    else:
        # Если ключ не указан, распаковываем всю модель.
        # Это работает для AddFriendsRequest и других.
        # model_dict -> {'count': 20, 'filters': {...}}
        # celery_kwargs -> {'count': 20, 'filters': {...}}
        celery_kwargs = model_dict

    task_result = task_func.apply_async(
        kwargs={'task_history_id': task_history.id, **celery_kwargs},
        queue='high_priority'
    )
    task_history.celery_task_id = task_result.id
    await db.commit()
    
    return ActionResponse(
        message=f"Задача '{task_history.task_name}' успешно добавлена в очередь.",
        task_id=task_result.id
    )

@router.post("/run/{task_key}", response_model=ActionResponse)
async def run_any_task(
    task_key: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Единый эндпоинт для запуска любой задачи."""
    _, RequestModel, _ = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not RequestModel:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    
    try:
        validated_data = RequestModel(**request)
    except Exception as e:
        # --- УЛУЧШЕНИЕ: Более детальное сообщение об ошибке ---
        error_detail = str(e)
        if "validation error" in error_detail:
             # Попытка извлечь более читаемое сообщение
            try:
                import json
                error_json = json.loads(error_detail)
                first_error = error_json[0]
                error_detail = f"Поле '{first_error['loc'][0]}': {first_error['msg']}"
            except:
                pass # Оставляем как есть, если не удалось распарсить
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_detail)

    return await _enqueue_task(current_user, db, task_key, validated_data)


@router.get("/history", response_model=PaginatedTasksResponse)
async def get_user_task_history(
    # ... остальная часть файла без изменений ...
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None)
):
    offset = (page - 1) * size
    base_query = select(TaskHistory).where(TaskHistory.user_id == current_user.id)
    if status:
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
# backend/app/api/endpoints/tasks.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi_limiter.depends import RateLimiter
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.db.models import User, TaskHistory, DelayProfile
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, ActionResponse,
    ViewStoriesRequest, LikeFriendsFeedRequest, RemoveFriendsRequest
)
from app.api.schemas.tasks import PaginatedTasksResponse
from app.tasks.runner import (
    accept_friend_requests, like_feed, add_recommended_friends,
    view_stories, like_friends_feed, remove_friends_by_criteria
)
from app.core.plans import is_automation_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG

router = APIRouter()

# Карта для ручного запуска задач.
TASK_ENDPOINT_MAP = {
    'accept_friends': accept_friend_requests,
    'like_feed': like_feed,
    'add_recommended': add_recommended_friends,
    'view_stories': view_stories,
    'like_friends_feed': like_friends_feed,
    'remove_friends': remove_friends_by_criteria,
}

class BehaviorStyle(BaseModel):
    delay_profile: DelayProfile

async def _enqueue_task(
    user: User,
    db: AsyncSession,
    task_key: str,
    request_data: BaseModel,
    behavior: BehaviorStyle
):
    """Универсальная функция для создания записи в TaskHistory и постановки задачи в очередь."""
    if not is_automation_available_for_plan(user.plan, task_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Действие недоступно на вашем тарифе '{user.plan}'."
        )

    task_func = TASK_ENDPOINT_MAP.get(task_key)
    if not task_func:
        raise HTTPException(status_code=404, detail="Задача с таким ключом не найдена или недоступна для ручного запуска.")
    
    task_config = next((item for item in AUTOMATIONS_CONFIG if item['id'] == task_key), None)
    task_name = task_config['name'] if task_config else "Неизвестная задача"

    task_kwargs = request_data.model_dump()
    task_kwargs['delay_profile'] = behavior.delay_profile.value
    
    task_history = TaskHistory(
        user_id=user.id,
        task_name=task_name,
        status="PENDING",
        parameters=task_kwargs
    )
    db.add(task_history)
    await db.flush()

    task_result = task_func.apply_async(
        kwargs={'task_history_id': task_history.id, **task_kwargs},
        queue='high_priority'
    )

    task_history.celery_task_id = task_result.id
    await db.commit()
    
    return ActionResponse(
        message=f"Задача '{task_history.task_name}' успешно добавлена в очередь.",
        task_id=task_result.id
    )

# --- Эндпоинты для ЗАПУСКА задач ---

@router.post("/run/accept-friends", response_model=ActionResponse, dependencies=[Depends(RateLimiter(times=20, minutes=1))])
async def run_accept_friends(
    request_data: AcceptFriendsRequest, 
    behavior: BehaviorStyle = Depends(), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await _enqueue_task(current_user, db, 'accept_friends', request_data, behavior)

@router.post("/run/like-feed", response_model=ActionResponse, dependencies=[Depends(RateLimiter(times=20, minutes=1))])
async def run_like_feed(
    request_data: LikeFeedRequest, 
    behavior: BehaviorStyle = Depends(), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await _enqueue_task(current_user, db, 'like_feed', request_data, behavior)

@router.post("/run/add-recommended-friends", response_model=ActionResponse, dependencies=[Depends(RateLimiter(times=20, minutes=1))])
async def run_add_recommended_friends(
    request_data: AddFriendsRequest, 
    behavior: BehaviorStyle = Depends(), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await _enqueue_task(current_user, db, 'add_recommended', request_data, behavior)

@router.post("/run/view-stories", response_model=ActionResponse, dependencies=[Depends(RateLimiter(times=20, minutes=1))])
async def run_view_stories(
    request_data: ViewStoriesRequest, 
    behavior: BehaviorStyle = Depends(), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await _enqueue_task(current_user, db, 'view_stories', request_data, behavior)

@router.post("/run/like-friends-feed", response_model=ActionResponse, dependencies=[Depends(RateLimiter(times=20, minutes=1))])
async def run_like_friends_feed(
    request_data: LikeFriendsFeedRequest, 
    behavior: BehaviorStyle = Depends(), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await _enqueue_task(current_user, db, 'like-friends-feed', request_data, behavior)

@router.post("/run/remove-friends", response_model=ActionResponse, dependencies=[Depends(RateLimiter(times=20, minutes=1))])
async def run_remove_friends(
    request_data: RemoveFriendsRequest, 
    behavior: BehaviorStyle = Depends(), 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await _enqueue_task(current_user, db, 'remove_friends', request_data, behavior)

# --- Эндпоинт для ПОЛУЧЕНИЯ ИСТОРИИ задач ---

@router.get("/history", response_model=PaginatedTasksResponse)
async def get_user_task_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None, description="Фильтр по статусу (напр., 'SUCCESS', 'FAILURE')")
):
    """
    Возвращает пагинированный список истории задач для текущего пользователя.
    """
    offset = (page - 1) * size
    
    tasks_query = (
        select(TaskHistory)
        .where(TaskHistory.user_id == current_user.id)
        .order_by(TaskHistory.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    
    count_query = (
        select(func.count(TaskHistory.id))
        .where(TaskHistory.user_id == current_user.id)
    )

    if status:
        tasks_query = tasks_query.where(TaskHistory.status == status.upper())
        count_query = count_query.where(TaskHistory.status == status.upper())
        
    tasks_result = await db.execute(tasks_query)
    total_result = await db.execute(count_query)
    
    tasks = tasks_result.scalars().all()
    total = total_result.scalar_one()

    return PaginatedTasksResponse(
        items=tasks,
        total=total,
        page=page,
        size=size,
        has_more=(offset + len(tasks)) < total
    )
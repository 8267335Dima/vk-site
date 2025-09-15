# backend/app/api/endpoints/tasks.py
from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Union
from pydantic import BaseModel
from arq.connections import ArqRedis

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile, get_arq_pool
from app.db.session import get_db
from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest,
    TaskConfigResponse, TaskField
)
from app.api.schemas.tasks import ActionResponse, PaginatedTasksResponse
from app.core.plans import get_plan_config, is_feature_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import TaskKey

router = APIRouter()

AnyTaskRequest = Union[
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest
]

# Карта задач теперь связывает ключ с именем функции в ARQ
TASK_FUNC_MAP = {
    TaskKey.ACCEPT_FRIENDS: "accept_friend_requests_task",
    TaskKey.LIKE_FEED: "like_feed_task",
    TaskKey.ADD_RECOMMENDED: "add_recommended_friends_task",
    TaskKey.VIEW_STORIES: "view_stories_task",
    TaskKey.REMOVE_FRIENDS: "remove_friends_by_criteria_task",
    TaskKey.MASS_MESSAGING: "mass_messaging_task",
    TaskKey.JOIN_GROUPS: "join_groups_by_criteria_task",
    TaskKey.LEAVE_GROUPS: "leave_groups_by_criteria_task",
    TaskKey.BIRTHDAY_CONGRATULATION: "birthday_congratulation_task",
    TaskKey.ETERNAL_ONLINE: "eternal_online_task",
}

async def _enqueue_task(
    user: User, db: AsyncSession, arq_pool: ArqRedis, task_key: str, request_data: BaseModel, original_task_name: Optional[str] = None
):
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

    task_func_name = TASK_FUNC_MAP.get(TaskKey(task_key))
    if not task_func_name:
        raise HTTPException(status_code=404, detail="Задача не найдена.")

    task_display_name = original_task_name
    if not task_display_name:
        task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key), None)
        task_display_name = task_config.name if task_config else "Неизвестная задача"

    task_history = TaskHistory(
        user_id=user.id,
        task_name=task_display_name,
        status="PENDING",
        parameters=request_data.model_dump(exclude_unset=True)
    )
    db.add(task_history)
    await db.commit()
    await db.refresh(task_history)

    job = await arq_pool.enqueue_job(
        task_func_name,
        task_history_id=task_history.id,
        # ARQ требует, чтобы все аргументы были именованными
        **request_data.model_dump()
    )

    # Сохраняем ID задачи ARQ для возможной отмены в будущем
    task_history.celery_task_id = job.job_id
    await db.commit()

    return ActionResponse(
        message=f"Задача '{task_display_name}' успешно добавлена в очередь.",
        task_id=job.job_id
    )

@router.get("/{task_key}/config", response_model=TaskConfigResponse, summary="Получить конфигурацию для задачи")
async def get_task_config(task_key: TaskKey, current_user: User = Depends(get_current_active_profile)):
    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key.value), None)
    if not task_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конфигурация для задачи не найдена.")

    user_limits = get_plan_config(current_user.plan).get("limits", {})
    fields = []

    if task_config.has_count_slider:
        max_val = 1000
        if task_key == TaskKey.ADD_RECOMMENDED:
            max_val = user_limits.get("daily_add_friends_limit", 40)
        elif task_key == TaskKey.LIKE_FEED:
            max_val = user_limits.get("daily_likes_limit", 1000)

        fields.append(TaskField(
            name="count",
            type="slider",
            label=task_config.modal_count_label or "Количество",
            default_value=task_config.default_count or 20,
            max_value=max_val
        ))

    return TaskConfigResponse(
        display_name=task_config.name,
        has_filters=task_config.has_filters,
        fields=fields
    )

@router.post("/run/{task_key}", response_model=ActionResponse)
async def run_any_task(
    task_key: TaskKey,
    request_data: AnyTaskRequest = Body(...),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    return await _enqueue_task(current_user, db, arq_pool, task_key.value, request_data)

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
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status not in ["PENDING", "STARTED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отменить можно только задачи в очереди или в процессе выполнения.")

    if task.celery_task_id:
        try:
            # Пытаемся отменить задачу в ARQ
            await arq_pool.abort_job(task.celery_task_id)
        except Exception as e:
            # Если задача уже не существует в Redis (например, уже выполнилась),
            # ARQ может выдать ошибку. Мы ее игнорируем.
            print(f"Ошибка при отмене задачи в ARQ (возможно, она уже завершилась): {e}")

    task.status = "CANCELLED"
    task.result = "Задача отменена пользователем."
    await db.commit()
    return {"message": "Запрос на отмену задачи отправлен."}

# <--- ИЗМЕНЕНИЕ: Реализация повтора задачи для ARQ --->
@router.post("/{task_history_id}/retry", response_model=ActionResponse)
async def retry_task(
    task_history_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status != "FAILURE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Повторить можно только задачу, завершившуюся с ошибкой.")

    task_key_str = next((item.id for item in AUTOMATIONS_CONFIG if item.name == task.task_name), None)
    if not task_key_str:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось определить тип задачи для повторного запуска.")

    # Получаем правильную Pydantic модель для валидации
    request_model_map = {
        TaskKey.ACCEPT_FRIENDS: AcceptFriendsRequest, TaskKey.LIKE_FEED: LikeFeedRequest,
        TaskKey.ADD_RECOMMENDED: AddFriendsRequest, TaskKey.VIEW_STORIES: EmptyRequest,
        TaskKey.REMOVE_FRIENDS: RemoveFriendsRequest, TaskKey.MASS_MESSAGING: MassMessagingRequest,
        TaskKey.JOIN_GROUPS: JoinGroupsRequest, TaskKey.LEAVE_GROUPS: LeaveGroupsRequest
    }
    RequestModel = request_model_map.get(TaskKey(task_key_str))
    if not RequestModel:
        raise HTTPException(status_code=500, detail="Не найдена модель запроса для задачи.")

    # Создаем новую задачу, используя параметры из старой
    validated_data = RequestModel(**(task.parameters or {}))

    return await _enqueue_task(
        current_user, db, arq_pool, task_key_str, validated_data, original_task_name=task.task_name
    )
# backend/app/api/endpoints/task_history.py

# ОТВЕТСТВЕННОСТЬ: Просмотр истории задач и управление ими (отмена, повтор).
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel
from arq.connections import ArqRedis

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile, get_arq_pool
from app.db.session import get_db
from app.api.schemas.tasks import ActionResponse, PaginatedTasksResponse
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import TaskKey

from .tasks import _enqueue_task
from app.tasks.task_maps import AnyTaskRequest, PREVIEW_SERVICE_MAP

router = APIRouter()

@router.get("/history", response_model=PaginatedTasksResponse, summary="Получить историю выполненных задач")
async def get_user_task_history(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None, description="Фильтр по статусу (PENDING, STARTED, SUCCESS, FAILURE, CANCELLED)")
):
    offset = (page - 1) * size
    base_query = select(TaskHistory).where(TaskHistory.user_id == current_user.id)
    if status and status.strip():
        base_query = base_query.where(TaskHistory.status == status.upper())

    tasks_query = base_query.order_by(TaskHistory.created_at.desc()).offset(offset).limit(size)
    count_query = select(func.count()).select_from(base_query.subquery())

    tasks = (await db.execute(tasks_query)).scalars().all()
    total = (await db.execute(count_query)).scalar_one()

    return PaginatedTasksResponse(items=tasks, total=total, page=page, size=size, has_more=(offset + len(tasks)) < total)


@router.post("/{task_history_id}/cancel", status_code=status.HTTP_202_ACCEPTED, summary="Отменить задачу")
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

    if task.arq_job_id:
        try:
            await arq_pool.abort_job(task.arq_job_id)
        except Exception:
            pass
    task.status = "CANCELLED"
    task.result = "Задача отменена пользователем."
    await db.commit()
    return {"message": "Запрос на отмену задачи отправлен."}


@router.post("/{task_history_id}/retry", response_model=ActionResponse, summary="Повторить неудавшуюся задачу")
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

    _, _, RequestModel = PREVIEW_SERVICE_MAP.get(TaskKey(task_key_str), (None, None, BaseModel))
    
    validated_data = RequestModel(**(task.parameters or {}))
    
    return await _enqueue_task(
        current_user, db, arq_pool, task_key_str, validated_data, original_task_name=task.task_name
    )
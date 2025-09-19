from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import List

from app.db.session import get_db
from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile
from pydantic import BaseModel

router = APIRouter()

# --- Зависимость для проверки прав администратора ---
async def get_current_admin_user(current_user: User = Depends(get_current_active_profile)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    return current_user

# --- Схемы для ответа API ---
class PerformanceDataItem(BaseModel):
    task_name: str
    total_runs: int
    failure_rate: float
    avg_duration: float | None

class PerformanceDataResponse(BaseModel):
    data: List[PerformanceDataItem]

# --- Сам эндпоинт ---
@router.get(
    "/dashboard/performance",
    response_model=PerformanceDataResponse,
    dependencies=[Depends(get_current_admin_user)]
)
async def get_performance_data(db: AsyncSession = Depends(get_db)):
    duration_sec = func.extract('epoch', TaskHistory.finished_at - TaskHistory.started_at)

    avg_duration_subq = (
        select(TaskHistory.task_name, func.avg(duration_sec).label("avg_duration"))
        .where(TaskHistory.status == "SUCCESS", TaskHistory.started_at.is_not(None), TaskHistory.finished_at.is_not(None))
        .group_by(TaskHistory.task_name).subquery()
    )

    status_counts_subq = (
        select(TaskHistory.task_name, func.count().label("total_runs"),
               func.sum(case((TaskHistory.status == "FAILURE", 1), else_=0)).label("failure_count"))
        .group_by(TaskHistory.task_name).subquery()
    )

    stmt = (
        select(status_counts_subq.c.task_name, status_counts_subq.c.total_runs,
               status_counts_subq.c.failure_count, avg_duration_subq.c.avg_duration)
        .join(avg_duration_subq, status_counts_subq.c.task_name == avg_duration_subq.c.task_name, isouter=True)
        .order_by(status_counts_subq.c.total_runs.desc())
    )
    
    result = await db.execute(stmt)
    performance_data = []
    for row in result.all():
        failure_rate = (row.failure_count / row.total_runs * 100) if row.total_runs > 0 else 0
        performance_data.append({
            "task_name": row.task_name,
            "total_runs": row.total_runs,
            "failure_rate": round(failure_rate, 2),
            "avg_duration": round(row.avg_duration, 2) if row.avg_duration else None
        })

    return PerformanceDataResponse(data=performance_data)
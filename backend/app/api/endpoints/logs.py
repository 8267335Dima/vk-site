# backend/app/api/endpoints/logs.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.session import get_db
from app.db.models import User, ActionLog
from app.api.dependencies import get_current_user
from app.api.schemas.logs import PaginatedLogsResponse, ActionLogEntry # <-- ИСПРАВЛЕННЫЙ ПУТЬ

router = APIRouter()

@router.get("", response_model=PaginatedLogsResponse)
async def get_user_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    action_type: Optional[str] = Query(None, description="Фильтр по типу действия (напр., 'friends')")
):
    """
    Возвращает пагинированный список логов действий для текущего пользователя.
    """
    offset = (page - 1) * size
    
    logs_query = (
        select(ActionLog)
        .where(ActionLog.user_id == current_user.id)
        .order_by(ActionLog.timestamp.desc())
        .offset(offset)
        .limit(size)
    )
    
    count_query = (
        select(func.count(ActionLog.id))
        .where(ActionLog.user_id == current_user.id)
    )

    if action_type:
        logs_query = logs_query.where(ActionLog.action_type == action_type)
        count_query = count_query.where(ActionLog.action_type == action_type)
        
    logs_result = await db.execute(logs_query)
    total_result = await db.execute(count_query)
    
    logs = logs_result.scalars().all()
    total = total_result.scalar_one()

    return PaginatedLogsResponse(
        items=logs,
        total=total,
        page=page,
        size=size,
        has_more=(offset + len(logs)) < total
    )
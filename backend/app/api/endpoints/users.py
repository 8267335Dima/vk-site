# backend/app/api/endpoints/users.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.models import User, DailyStats, Proxy
from app.api.dependencies import get_current_user
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository

router = APIRouter()

class UserMeResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    photo_200: str
    status: str = ""
    counters: Optional[Dict[str, Any]] = None
    plan: str
    plan_expires_at: Optional[datetime] = None
    is_admin: bool
    delay_profile: str
    is_plan_active: bool
    # --- ИЗМЕНЕНИЕ: Убираем прокси отсюда, будет отдельный менеджер ---

@router.get("/me", response_model=UserMeResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Получает полную информацию о текущем пользователе из VK и нашей БД."""
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    
    user_info_vk = await vk_api.get_user_info()
    if not user_info_vk:
        raise HTTPException(status_code=404, detail="Не удалось получить информацию из VK.")

    is_plan_active = True
    if current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        is_plan_active = False
    
    response_data = {
        **user_info_vk,
        "plan": current_user.plan,
        "plan_expires_at": current_user.plan_expires_at,
        "is_admin": current_user.is_admin,
        "delay_profile": current_user.delay_profile.value,
        "is_plan_active": is_plan_active
    }
    
    return response_data

# --- НОВЫЙ ЭНДПОИНТ И СХЕМА ДЛЯ ВИДЖЕТА ЛИМИТОВ ---
class DailyLimitsResponse(BaseModel):
    likes_limit: int
    likes_today: int
    friends_add_limit: int
    friends_add_today: int

@router.get("/me/limits", response_model=DailyLimitsResponse)
async def get_daily_limits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает текущие дневные лимиты и использование."""
    stats_repo = StatsRepository(db)
    today_stats = await stats_repo.get_or_create_today_stats(current_user.id)

    return DailyLimitsResponse(
        likes_limit=current_user.daily_likes_limit,
        likes_today=today_stats.likes_count,
        friends_add_limit=current_user.daily_add_friends_limit,
        friends_add_today=today_stats.friends_added_count
    )

class TaskInfoResponse(BaseModel):
    count: int

@router.get("/task-info", response_model=TaskInfoResponse)
async def get_task_info(
    task_key: Literal['accept_friends', 'remove_friends'] = Query(...),
    current_user: User = Depends(get_current_user),
):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    
    count = 0
    if task_key == 'accept_friends':
        response = await vk_api.get_incoming_friend_requests(count=0)
        count = response.get('count', 0) if response else 0
    elif task_key == 'remove_friends':
        response = await vk_api.get_user_friends(current_user.vk_id)
        count = len(response) if response else 0
    
    return TaskInfoResponse(count=count)
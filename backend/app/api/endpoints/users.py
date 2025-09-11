# backend/app/api/endpoints/users.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import User, DelayProfile
from app.api.dependencies import get_current_user
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository
# --- НОВЫЙ ИМПОРТ ---
from app.core.plans import get_features_for_plan, is_feature_available_for_plan


router = APIRouter()

# --- Схемы ---
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
    # --- НОВОЕ ПОЛЕ ---
    available_features: List[str]

class DailyLimitsResponse(BaseModel):
    likes_limit: int
    likes_today: int
    friends_add_limit: int
    friends_add_today: int

class UpdateDelayProfileRequest(BaseModel):
    delay_profile: DelayProfile

class TaskInfoResponse(BaseModel):
    count: int

# --- Эндпоинты ---

@router.get("/me", response_model=UserMeResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Получает полную информацию о текущем пользователе из VK и нашей БД."""
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    if not vk_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Токен доступа недействителен. Пожалуйста, авторизуйтесь заново.")
        
    vk_api = VKAPI(access_token=vk_token)
    
    try:
        user_info_vk = await vk_api.get_user_info()
    except VKAPIError as e:
         raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=f"Ошибка VK API: {e.message}")

    if not user_info_vk:
        raise HTTPException(status_code=404, detail="Не удалось получить информацию из VK.")

    is_plan_active = True
    plan_name = current_user.plan
    if current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        is_plan_active = False
        plan_name = "Expired" # Используем специальное имя для фронтенда

    # --- ИЗМЕНЕНИЕ: Получаем список доступных фич ---
    features = get_features_for_plan(plan_name)
    
    return {
        **user_info_vk,
        "plan": current_user.plan,
        "plan_expires_at": current_user.plan_expires_at,
        "is_admin": current_user.is_admin,
        "delay_profile": current_user.delay_profile.value,
        "is_plan_active": is_plan_active,
        "available_features": features, # <--- Передаем их в ответе
    }

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

@router.put("/me/delay-profile", response_model=UserMeResponse)
async def update_user_delay_profile(
    request_data: UpdateDelayProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Обновляет профиль задержек (скорость работы) пользователя."""
    # --- ИЗМЕНЕНИЕ: Проверяем доступ к фиче перед изменением ---
    feature_key = 'fast_slow_delay_profile'
    if request_data.delay_profile != DelayProfile.normal and not is_feature_available_for_plan(current_user.plan, feature_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Смена скорости доступна только на PRO тарифе.")
        
    current_user.delay_profile = request_data.delay_profile
    await db.commit()
    # После коммита нужно получить обновленные данные, включая user_info_vk
    return await read_users_me(current_user)

@router.get("/task-info", response_model=TaskInfoResponse)
async def get_task_info(
    task_key: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Возвращает предзагруженную информацию для модальных окон (напр. кол-во заявок)."""
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
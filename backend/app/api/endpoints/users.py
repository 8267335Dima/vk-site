# --- backend/app/api/endpoints/users.py ---
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.db.session import get_db
from app.db.models import ManagedProfile, User, DelayProfile, FilterPreset
from app.api.dependencies import get_current_active_profile, get_current_manager_user
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository
from app.core.plans import get_features_for_plan, is_feature_available_for_plan
from app.api.schemas.users import TaskInfoResponse, FilterPresetCreate, FilterPresetRead

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
    available_features: List[str]

class DailyLimitsResponse(BaseModel):
    likes_limit: int
    likes_today: int
    friends_add_limit: int
    friends_add_today: int

class UpdateDelayProfileRequest(BaseModel):
    delay_profile: DelayProfile

@router.get("/me", response_model=UserMeResponse)
async def read_users_me(current_user: User = Depends(get_current_active_profile)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    if not vk_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Токен доступа недействителен. Пожалуйста, авторизуйтесь заново."
        )
        
    vk_api = VKAPI(access_token=vk_token)
    
    try:
        user_info_vk_list = await vk_api.get_user_info(fields="photo_200,status,counters")
        user_info_vk = user_info_vk_list[0] if user_info_vk_list else {}
    except VKAPIError as e:
         raise HTTPException(
             status_code=status.HTTP_424_FAILED_DEPENDENCY, 
             detail=f"Ошибка VK API: {e.message}"
        )

    if not user_info_vk:
        raise HTTPException(status_code=404, detail="Не удалось получить информацию из VK.")

    is_plan_active = True
    plan_name = current_user.plan
    if current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        is_plan_active = False
        plan_name = "Expired"

    features = get_features_for_plan(plan_name)
    
    return {
        **user_info_vk,
        "plan": current_user.plan,
        "plan_expires_at": current_user.plan_expires_at,
        "is_admin": current_user.is_admin,
        "delay_profile": current_user.delay_profile.value,
        "is_plan_active": is_plan_active,
        "available_features": features,
    }

@router.get("/me/limits", response_model=DailyLimitsResponse)
async def get_daily_limits(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
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
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    feature_key = 'fast_slow_delay_profile'
    if request_data.delay_profile != DelayProfile.normal and not is_feature_available_for_plan(current_user.plan, feature_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Смена скорости доступна только на PRO тарифе.")
        
    current_user.delay_profile = request_data.delay_profile
    await db.commit()
    await db.refresh(current_user)
    # Refreshing user info from VK to return the most up-to-date data
    return await read_users_me(current_user)

@router.get("/task-info", response_model=TaskInfoResponse)
async def get_task_info(
    task_key: str = Query(...),
    current_user: User = Depends(get_current_active_profile)
):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    count = 0

    try:
        if task_key == "accept_friends":
            response = await vk_api.get_incoming_friend_requests()
            count = response.get("count", 0) if response else 0
        
        elif task_key == "remove_friends":
            user_info_list = await vk_api.get_user_info(user_ids=str(current_user.vk_id), fields="counters")
            if user_info_list:
                user_info = user_info_list[0]
                count = user_info.get("counters", {}).get("friends", 0)

    except VKAPIError as e:
        print(f"Could not fetch task info for {task_key} due to VK API error: {e}")
        count = 0

    return TaskInfoResponse(count=count)

@router.get("/me/filter-presets", response_model=List[FilterPresetRead])
async def get_filter_presets(
    action_type: str = Query(...),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(FilterPreset).where(
        FilterPreset.user_id == current_user.id,
        FilterPreset.action_type == action_type
    ).order_by(FilterPreset.name)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/me/filter-presets", response_model=FilterPresetRead, status_code=status.HTTP_201_CREATED)
async def create_filter_preset(
    preset_data: FilterPresetCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    new_preset = FilterPreset(user_id=current_user.id, **preset_data.model_dump())
    db.add(new_preset)
    try:
        await db.commit()
        await db.refresh(new_preset)
        return new_preset
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пресет с таким названием для данного действия уже существует."
        )

@router.delete("/me/filter-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter_preset(
    preset_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    stmt = delete(FilterPreset).where(
        FilterPreset.id == preset_id,
        FilterPreset.user_id == current_user.id
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пресет не найден.")
    await db.commit()


class ManagedProfileRead(BaseModel):
    id: int
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str
    
    class Config:
        from_attributes = True

@router.get("/me/managed-profiles", response_model=List[ManagedProfileRead], summary="Получить список профилей для переключения")
async def get_managed_profiles(
    manager: User = Depends(get_current_manager_user),
    db: AsyncSession = Depends(get_db)
):
    # Загружаем связи с профилями и сами профили
    result = await db.execute(
        select(User)
        .options(selectinload(User.managed_profiles).selectinload(ManagedProfile.profile))
        .where(User.id == manager.id)
    )
    manager_with_profiles = result.scalar_one()

    # Собираем информацию о всех профилях, включая самого менеджера
    profiles_info = []
    
    # 1. Добавляем самого менеджера
    manager_info_vk = await VKAPI(access_token=decrypt_data(manager.encrypted_vk_token)).get_user_info(fields="photo_50")
    profiles_info.append({
        "id": manager.id,
        "vk_id": manager.vk_id,
        "first_name": manager_info_vk.get("first_name", ""),
        "last_name": manager_info_vk.get("last_name", ""),
        "photo_50": manager_info_vk.get("photo_50", "")
    })
    
    # 2. Добавляем управляемые профили
    for managed_rel in manager_with_profiles.managed_profiles:
        profile = managed_rel.profile
        profile_info_vk = await VKAPI(access_token=decrypt_data(profile.encrypted_vk_token)).get_user_info(fields="photo_50")
        profiles_info.append({
            "id": profile.id,
            "vk_id": profile.vk_id,
            "first_name": profile_info_vk.get("first_name", ""),
            "last_name": profile_info_vk.get("last_name", ""),
            "photo_50": profile_info_vk.get("photo_50", "")
        })

    return profiles_info
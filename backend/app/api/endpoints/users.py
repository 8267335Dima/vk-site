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
from app.api.schemas.users import TaskInfoResponse, FilterPresetCreate, FilterPresetRead, ManagedProfileRead, AnalyticsSettingsRead, AnalyticsSettingsUpdate
from app.core.enums import PlanName, FeatureKey

router = APIRouter()

class UserMeResponse(BaseModel):
    id: int
    vk_id: int
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
        user_info_vk_list = await vk_api.users.get(fields="photo_200,status,counters")
    except VKAPIError as e:
         raise HTTPException(
             status_code=status.HTTP_424_FAILED_DEPENDENCY, 
             detail=f"Ошибка VK API: {e.message}"
        )
    finally:
        await vk_api.close()

    if not user_info_vk_list or not isinstance(user_info_vk_list, list):
        raise HTTPException(status_code=404, detail="Не удалось получить информацию из VK.")
    
    user_info_vk = user_info_vk_list[0]

    is_plan_active = True
    plan_name = current_user.plan.name_id
    if current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        is_plan_active = False
        plan_name = PlanName.EXPIRED.name

    features = get_features_for_plan(plan_name)
    
    return {
        **user_info_vk,
        "id": current_user.id,
        "vk_id": current_user.vk_id,
        "plan": current_user.plan.display_name,
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
    if request_data.delay_profile != DelayProfile.normal and not await is_feature_available_for_plan(current_user.plan.name_id, FeatureKey.FAST_SLOW_DELAY_PROFILE, user=current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Смена скорости доступна только на PRO тарифе.")
        
    current_user.delay_profile = request_data.delay_profile
    await db.commit()
    await db.refresh(current_user)
    return await read_users_me(current_user)

@router.post("/me/filter-presets", response_model=FilterPresetRead, status_code=status.HTTP_201_CREATED)
async def create_filter_preset(
    preset_data: FilterPresetCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Создает новый пресет фильтров для пользователя."""
    stmt = select(FilterPreset).where(
        FilterPreset.user_id == current_user.id,
        FilterPreset.name == preset_data.name,
        FilterPreset.action_type == preset_data.action_type
    )
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пресет с таким названием для данного действия уже существует."
        )
    
    new_preset = FilterPreset(
        user_id=current_user.id,
        **preset_data.model_dump()
    )
    db.add(new_preset)
    try:
        await db.commit()
        await db.refresh(new_preset)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пресет с таким названием для данного действия уже существует."
        )
    return new_preset

@router.get("/me/filter-presets", response_model=List[FilterPresetRead])
async def get_filter_presets(
    action_type: str = Query(...),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает список пресетов фильтров для определенного действия."""
    stmt = select(FilterPreset).where(
        FilterPreset.user_id == current_user.id,
        FilterPreset.action_type == action_type
    ).order_by(FilterPreset.name)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/me/managed-profiles", response_model=List[ManagedProfileRead])
async def get_managed_profiles(
    manager: User = Depends(get_current_manager_user),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает список профилей, которыми управляет текущий пользователь (менеджер), включая его собственный."""
    await db.refresh(manager, attribute_names=['managed_profiles'])
    
    all_profiles_in_db = [manager] + [mp.profile for mp in manager.managed_profiles]
    all_vk_ids = {p.vk_id for p in all_profiles_in_db}
    
    vk_info_map = {}
    if all_vk_ids:
        vk_api = VKAPI(decrypt_data(manager.encrypted_vk_token))
        try:
            vk_ids_str = ",".join(map(str, all_vk_ids))
            user_infos = await vk_api.users.get(user_ids=vk_ids_str, fields="photo_50")
            if user_infos:
                vk_info_map = {info['id']: info for info in user_infos}
        except VKAPIError:
            pass # Игнорируем ошибки VK, чтобы вернуть хотя бы данные из нашей БД
        finally:
            await vk_api.close()

    response_data = []
    for profile in all_profiles_in_db:
        vk_info = vk_info_map.get(profile.vk_id, {})
        response_data.append(ManagedProfileRead(
            id=profile.id,
            vk_id=profile.vk_id,
            first_name=vk_info.get("first_name", "N/A"),
            last_name=vk_info.get("last_name", ""),
            photo_50=vk_info.get("photo_50", "")
        ))
    return response_data

@router.put(
    "/me/analytics-settings",
    response_model=AnalyticsSettingsRead,
    response_model_by_alias=False 
)
async def update_analytics_settings(
    settings_data: AnalyticsSettingsUpdate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Обновляет настройки аналитики для пользователя."""
    current_user.analytics_settings_posts_count = settings_data.posts_count
    current_user.analytics_settings_photos_count = settings_data.photos_count
    await db.commit()
    await db.refresh(current_user)
    return current_user

@router.get(
    "/me/analytics-settings",
    response_model=AnalyticsSettingsRead,
    response_model_by_alias=False  
)
async def get_analytics_settings(
    current_user: User = Depends(get_current_active_profile)
):
    """Возвращает текущие настройки аналитики пользователя."""
    return current_user
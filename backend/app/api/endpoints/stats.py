# backend/app/api/endpoints/stats.py
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi_cache.decorator import cache

from app.db.session import get_db
from app.db.models import User, DailyStats
from app.api.dependencies import get_current_active_profile
from app.api.schemas.stats import (
    FriendsAnalyticsResponse, ActivityStatsResponse, DailyActivity,
    FriendsDynamicResponse, FriendsDynamicItem
)
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data

router = APIRouter()

@router.get("/friends-analytics", response_model=FriendsAnalyticsResponse)
@cache(expire=3600) # Кешируем на 1 час
async def get_friends_analytics(current_user: User = Depends(get_current_active_profile)):
    """Возвращает гендерное распределение друзей. Результат кэшируется."""
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    # Прокси для этого запроса не так важен, но можно добавить при необходимости
    vk_api = VKAPI(access_token=vk_token, proxy=None)
    
    try:
        friends_response = await vk_api.get_user_friends(user_id=current_user.vk_id, fields="sex")
    except VKAPIError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=f"Ошибка VK API: {e.message}")
    finally:
        # --- ИСПРАВЛЕНИЕ: Гарантированно закрываем сессию ---
        if vk_api:
            await vk_api.close()

    analytics = {"male_count": 0, "female_count": 0, "other_count": 0}
    if friends_response and isinstance(friends_response.get('items'), list):
        # Итерируемся по списку друзей, а не по всему словарю
        for friend in friends_response['items']:
            sex = friend.get("sex")
            if sex == 1:
                analytics["female_count"] += 1
            elif sex == 2:
                analytics["male_count"] += 1
            else:
                analytics["other_count"] += 1
    return FriendsAnalyticsResponse(**analytics)

@router.get("/activity", response_model=ActivityStatsResponse)
async def get_activity_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_profile)
):
    """Возвращает статистику по действиям за последние N дней."""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)
    
    query = (
        select(DailyStats)
        .where(DailyStats.user_id == current_user.id)
        .where(DailyStats.date >= start_date)
        .order_by(DailyStats.date)
    )
    result = await db.execute(query)
    stats = result.scalars().all()
    
    stats_map = {s.date: s for s in stats}
    
    response_data = []
    for i in range(days):
        current_date = start_date + datetime.timedelta(days=i)
        stat_entry = stats_map.get(current_date)
        if stat_entry:
            response_data.append(DailyActivity(
                date=current_date,
                likes=stat_entry.likes_count,
                friends_added=stat_entry.friends_added_count,
                requests_accepted=stat_entry.friend_requests_accepted_count
            ))
        else:
            response_data.append(DailyActivity(
                date=current_date,
                likes=0,
                friends_added=0,
                requests_accepted=0
            ))
            
    return ActivityStatsResponse(period_days=days, data=response_data)
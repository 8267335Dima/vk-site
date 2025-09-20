# backend/app/api/endpoints/stats.py
import asyncio
import datetime
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from fastapi_cache.decorator import cache
from app.db.models import UserActivity
from sqlalchemy import desc
from app.db.session import AsyncSessionFactory, get_db, get_read_db
from app.db.models import User, DailyStats
from app.api.dependencies import get_current_active_profile
from app.api.schemas.stats import (
    FriendsAnalyticsResponse, ActivityStatsResponse, DailyActivity,
    FriendsDynamicResponse, FriendsDynamicItem
)
from pydantic import BaseModel
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.api.schemas.analytics import ProfileGrowthResponse
from app.api.endpoints.analytics import get_profile_growth_analytics

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
        for friend in friends_response['items']:
            sex = friend.get("sex")
            if sex == 1:
                analytics["female_count"] += 1
            elif sex == 2:
                analytics["male_count"] += 1
            else:
                analytics["other_count"] += 1
    return analytics

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


class ActivitySource(BaseModel):
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str
    count: int

@router.get("/activity-sources", response_model=List[ActivitySource])
async def get_activity_sources(
    activity_type: Literal['like', 'comment'],
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает топ N пользователей по лайкам или комментариям."""
    stmt = select(UserActivity).where(
        UserActivity.user_id == current_user.id,
        UserActivity.activity_type == activity_type
    ).order_by(desc(UserActivity.count)).limit(limit)
    
    result = await db.execute(stmt)
    top_activities = result.scalars().all()
    if not top_activities: 
        return []

    # --- ПОЛНАЯ РЕАЛИЗАЦИЯ ЛОГИКИ ВМЕСТО ЗАГЛУШКИ ---
    
    # 1. Собираем VK ID всех пользователей из топа
    source_vk_ids = {activity.source_vk_id for activity in top_activities}
    
    vk_info_map = {}
    vk_api = None
    try:
        # 2. Получаем информацию о них одним запросом к VK API
        vk_token = decrypt_data(current_user.encrypted_vk_token)
        if not vk_token:
             raise HTTPException(status_code=403, detail="Невалидный токен VK")
        
        vk_api = VKAPI(access_token=vk_token)
        vk_ids_str = ",".join(map(str, source_vk_ids))
        user_infos = await vk_api.users.get(user_ids=vk_ids_str, fields="photo_50")
        if user_infos:
            vk_info_map = {info['id']: info for info in user_infos}
    except VKAPIError as e:
        # Если VK API недоступен, мы можем вернуть только ID и количество,
        # но лучше сообщить об ошибке
        raise HTTPException(status_code=503, detail=f"Ошибка при получении данных от VK: {e.message}")
    finally:
        if vk_api:
            await vk_api.close()

    # 3. Собираем финальный ответ, объединяя данные из нашей БД и из VK
    response_data = []
    for activity in top_activities:
        vk_info = vk_info_map.get(activity.source_vk_id)
        if vk_info: # Добавляем в ответ, только если смогли получить инфо из VK
            response_data.append(ActivitySource(
                vk_id=activity.source_vk_id,
                first_name=vk_info.get("first_name", "DELETED"),
                last_name=vk_info.get("last_name", ""),
                photo_50=vk_info.get("photo_50", ""),
                count=activity.count
            ))
            
    return response_data

class PulseEvent(BaseModel):
    timestamp: datetime
    event_type: Literal['action', 'like', 'comment']
    message: str
    source_vk_id: Optional[int] = None
    source_name: Optional[str] = None
    source_photo: Optional[str] = None

class PulseResponse(BaseModel):
    growth_chart: ProfileGrowthResponse
    unread_messages: int
    incoming_requests: int
    events: List[PulseEvent]

@router.get("/dashboard/pulse", response_model=PulseResponse)
async def get_dashboard_pulse(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_read_db)
):
    vk_api = VKAPI(decrypt_data(current_user.encrypted_vk_token))

    try:
        growth_task = get_profile_growth_analytics(days=7, current_user=current_user, db=db)
        conv_task = vk_api.messages.getConversations(count=0, filter='unread')
        req_task = vk_api.friends.getRequests(count=0)

        event_query = text(f"""
            (SELECT created_at as timestamp, 'action' as event_type, task_name as message, NULL as source_vk_id 
             FROM task_history 
             WHERE user_id = :user_id AND status = 'SUCCESS')
            UNION ALL
            (SELECT created_at as timestamp, 'like' as event_type, 'лайкнул(а) ваш контент' as message, source_vk_id 
             FROM user_activities 
             WHERE user_id = :user_id AND activity_type = 'like')
            UNION ALL
            (SELECT created_at as timestamp, 'comment' as event_type, 'прокомментировал(а) ваш контент' as message, source_vk_id 
             FROM user_activities 
             WHERE user_id = :user_id AND activity_type = 'comment')
            ORDER BY timestamp DESC
            LIMIT 30
        """)
        events_task = db.execute(event_query, {"user_id": current_user.id})

        results = await asyncio.gather(growth_task, conv_task, req_task, events_task, return_exceptions=True)
    finally:
        await vk_api.close()

    growth_data = results[0] if not isinstance(results[0], Exception) else ProfileGrowthResponse(data=[])
    conv_data = results[1] if not isinstance(results[1], Exception) else {}
    req_data = results[2] if not isinstance(results[2], Exception) else {}
    events_raw = results[3].all() if not isinstance(results[3], Exception) else []

    source_vk_ids = {row.source_vk_id for row in events_raw if row.source_vk_id}
    vk_info_map = {}
    if source_vk_ids:
        async with VKAPI(decrypt_data(current_user.encrypted_vk_token)) as vk_api_enrich:
            user_infos = await vk_api_enrich.users.get(user_ids=",".join(map(str, source_vk_ids)), fields="photo_50")
            if user_infos:
                vk_info_map = {info['id']: info for info in user_infos}

    event_list = []
    for row in events_raw:
        source_info = vk_info_map.get(row.source_vk_id)
        source_name = f"{source_info['first_name']} {source_info['last_name']}" if source_info else None
        event_list.append(PulseEvent(
            timestamp=row.timestamp,
            event_type=row.event_type,
            message=row.message,
            source_vk_id=row.source_vk_id,
            source_name=source_name,
            source_photo=source_info['photo_50'] if source_info else None
        ))
    
    return PulseResponse(
        growth_chart=growth_data,
        unread_messages=conv_data.get('count', 0),
        incoming_requests=req_data.get('count', 0),
        events=event_list
    )
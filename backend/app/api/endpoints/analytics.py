# backend/app/api/endpoints/analytics.py
import datetime
from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, ProfileMetric, FriendRequestLog, PostActivityHeatmap
from app.api.dependencies import get_current_active_profile
from app.db.session import get_db
from app.api.schemas.analytics import (
    AudienceAnalyticsResponse, ProfileGrowthResponse, ProfileGrowthItem,
    ProfileSummaryResponse, FriendRequestConversionResponse, PostActivityHeatmapResponse
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.services.analytics_service import AnalyticsService
from app.services.event_emitter import SystemLogEmitter 

router = APIRouter()


@router.get("/audience", response_model=AudienceAnalyticsResponse)
@cache(expire=21600)
async def get_audience_analytics(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    emitter = SystemLogEmitter(task_name="analytics_endpoint") 
    service = AnalyticsService(db=db, user=current_user, emitter=emitter)
    # Используем try-finally для гарантированного закрытия сессии
    try:
        return await service.get_audience_distribution()
    finally:
        if service.vk_api:
            await service.vk_api.close()


@router.get("/profile-summary", response_model=ProfileSummaryResponse)
@cache(expire=3600)
async def get_profile_summary(current_user: User = Depends(get_current_active_profile)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    
    try:
        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        user_info_list = await vk_api.users.get(user_ids=str(current_user.vk_id), fields="counters")
        user_info = user_info_list[0] if user_info_list else {}
        
        counters = user_info.get('counters', {})
        wall_info = await vk_api.wall.get(owner_id=current_user.vk_id, count=0)
    finally:
        await vk_api.close()
    
    return ProfileSummaryResponse(
        friends=counters.get('friends', 0),
        followers=counters.get('followers', 0),
        photos=counters.get('photos', 0),
        wall_posts=wall_info.get('count', 0) if wall_info else 0
    )


@router.get("/profile-growth", response_model=ProfileGrowthResponse)
async def get_profile_growth_analytics(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    # ... (код без изменений)
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)

    stmt = (
        select(ProfileMetric)
        .where(
            ProfileMetric.user_id == current_user.id,
            ProfileMetric.date.between(start_date, end_date)
        )
        .order_by(ProfileMetric.date)
    )
    result = await db.execute(stmt)
    data = result.scalars().all()
    
    response_data = [
        ProfileGrowthItem(
            date=row.date, 
            total_likes_on_content=row.total_likes_on_content,
            friends_count=row.friends_count
        ) for row in data
    ]

    return ProfileGrowthResponse(data=response_data)


@router.get("/friend-request-conversion", response_model=FriendRequestConversionResponse)
async def get_friend_request_conversion_stats(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):

    stmt = (
        select(FriendRequestLog.status, func.count(FriendRequestLog.id))
        .where(FriendRequestLog.user_id == current_user.id)
        .group_by(FriendRequestLog.status)
    )
    result = await db.execute(stmt)
    stats = {status.name: count for status, count in result.all()}

    sent_total = stats.get('pending', 0) + stats.get('accepted', 0)
    accepted_total = stats.get('accepted', 0)
    
    conversion_rate = (accepted_total / sent_total * 100) if sent_total > 0 else 0

    return FriendRequestConversionResponse(
        sent_total=sent_total,
        accepted_total=accepted_total,
        conversion_rate=conversion_rate
    )


@router.get("/post-activity-heatmap", response_model=PostActivityHeatmapResponse)
async def get_post_activity_heatmap(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):

    stmt = select(PostActivityHeatmap).where(PostActivityHeatmap.user_id == current_user.id)
    result = await db.execute(stmt)
    heatmap_data = result.scalar_one_or_none()
    
    if not heatmap_data:
        return PostActivityHeatmapResponse(data=[[0]*24]*7)
        
    return PostActivityHeatmapResponse(data=heatmap_data.heatmap_data.get("data", [[0]*24]*7))
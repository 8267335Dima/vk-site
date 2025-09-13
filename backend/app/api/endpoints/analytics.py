# --- backend/app/api/endpoints/analytics.py ---
import datetime
from collections import Counter
from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FriendsHistory, User, DailyStats, ProfileMetric, FriendRequestLog, FriendRequestStatus
from app.api.dependencies import get_current_active_profile
from app.db.session import get_db
from app.api.schemas.analytics import (
    AudienceAnalyticsResponse, AudienceStatItem, 
    SexDistributionResponse,
    ProfileGrowthResponse, ProfileGrowthItem,
    ProfileSummaryResponse, FriendRequestConversionResponse
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.db.models import PostActivityHeatmap
from app.api.schemas.analytics import PostActivityHeatmapResponse

router = APIRouter()


def calculate_age(bdate: str) -> int | None:
    try:
        parts = bdate.split('.')
        if len(parts) == 3:
            birth_date = datetime.datetime.strptime(bdate, "%d.%m.%Y")
            today = datetime.date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except (ValueError, TypeError):
        return None
    return None

def get_age_group(age: int) -> str:
    if age < 18: return "< 18"
    if 18 <= age <= 24: return "18-24"
    if 25 <= age <= 34: return "25-34"
    if 35 <= age <= 44: return "35-44"
    if age >= 45: return "45+"
    return "Не указан"

@router.get("/audience", response_model=AudienceAnalyticsResponse)
@cache(expire=21600)
async def get_audience_analytics(current_user: User = Depends(get_current_active_profile)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)

    friends = await vk_api.get_user_friends(user_id=current_user.vk_id, fields="sex,bdate,city")
    if not friends:
        return AudienceAnalyticsResponse(city_distribution=[], age_distribution=[], sex_distribution=[])

    city_counter = Counter(
        friend['city']['title']
        for friend in friends
        if friend.get('city') and friend.get('city', {}).get('title') and not friend.get('deactivated')
    )
    top_cities = [
        AudienceStatItem(name=city, value=count)
        for city, count in city_counter.most_common(5)
    ]

    ages = [calculate_age(friend['bdate']) for friend in friends if friend.get('bdate') and not friend.get('deactivated')]
    age_groups = [get_age_group(age) for age in ages if age is not None]
    age_counter = Counter(age_groups)
    
    age_distribution = [
        AudienceStatItem(name=group, value=count)
        for group, count in sorted(age_counter.items())
    ]

    sex_counter = Counter(
        'Мужчины' if f.get('sex') == 2 else ('Женщины' if f.get('sex') == 1 else 'Не указан')
        for f in friends if not f.get('deactivated')
    )
    sex_distribution = [SexDistributionResponse(name=k, value=v) for k, v in sex_counter.items()]

    return AudienceAnalyticsResponse(
        city_distribution=top_cities,
        age_distribution=age_distribution,
        sex_distribution=sex_distribution
    )

@router.get("/profile-summary", response_model=ProfileSummaryResponse)
@cache(expire=3600)
async def get_profile_summary(current_user: User = Depends(get_current_active_profile)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    
    user_info_list = await vk_api.get_user_info(user_ids=str(current_user.vk_id), fields="counters")
    user_info = user_info_list[0] if user_info_list else {}
    
    friends = user_info.get('counters', {}).get('friends', 0)
    followers = user_info.get('counters', {}).get('followers', 0)
    photos = user_info.get('counters', {}).get('photos', 0)
    
    wall_info = await vk_api.get_wall(owner_id=current_user.vk_id, count=0)
    wall_posts = wall_info.get('count', 0) if wall_info else 0
    
    return ProfileSummaryResponse(
        friends=friends,
        followers=followers,
        photos=photos,
        wall_posts=wall_posts
    )

@router.get("/profile-growth", response_model=ProfileGrowthResponse)
async def get_profile_growth_analytics(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
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
        return PostActivityHeatmapResponse(data=[[0]*24]*7) # Возвращаем пустую матрицу
        
    return PostActivityHeatmapResponse(data=heatmap_data.heatmap_data.get("data", [[0]*24]*7))
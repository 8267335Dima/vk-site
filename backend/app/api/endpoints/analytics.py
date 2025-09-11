# backend/app/api/endpoints/analytics.py
import datetime
from collections import Counter
from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FriendsHistory, User, DailyStats
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.api.schemas.analytics import (
    AudienceAnalyticsResponse, AudienceStatItem, 
    FriendsDynamicItem, FriendsDynamicResponse,
    ActionSummaryResponse, ActionSummaryItem,
    SexDistributionResponse
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data

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
async def get_audience_analytics(current_user: User = Depends(get_current_user)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)

    friends = await vk_api.get_user_friends(user_id=current_user.vk_id, fields="sex,bdate,city")
    if not friends:
        return AudienceAnalyticsResponse(city_distribution=[], age_distribution=[], sex_distribution=[])

    # --- Анализ по городам ---
    city_counter = Counter(
        friend['city']['title']
        for friend in friends
        if friend.get('city') and friend.get('city', {}).get('title') and not friend.get('deactivated')
    )
    top_cities = [
        AudienceStatItem(name=city, value=count)
        for city, count in city_counter.most_common(5)
    ]

    # --- Анализ по возрасту ---
    ages = [calculate_age(friend['bdate']) for friend in friends if friend.get('bdate') and not friend.get('deactivated')]
    age_groups = [get_age_group(age) for age in ages if age is not None]
    age_counter = Counter(age_groups)
    
    age_distribution = [
        AudienceStatItem(name=group, value=count)
        for group, count in sorted(age_counter.items())
    ]

    # --- Анализ по полу ---
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

@router.get("/friends-dynamic", response_model=FriendsDynamicResponse)
async def get_friends_dynamic(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)

    stmt = (
        select(FriendsHistory.date, FriendsHistory.friends_count)
        .where(
            FriendsHistory.user_id == current_user.id,
            FriendsHistory.date.between(start_date, end_date)
        )
        .order_by(FriendsHistory.date)
    )

    result = await db.execute(stmt)
    data = result.all()

    response_data = [
        FriendsDynamicItem(date=row.date, total_friends=row.friends_count)
        for row in data
    ]

    return FriendsDynamicResponse(data=response_data)

@router.get("/actions-summary", response_model=ActionSummaryResponse)
async def get_actions_summary(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)

    stmt = (
        select(
            DailyStats.date,
            (
                DailyStats.likes_count +
                DailyStats.friends_added_count +
                DailyStats.friend_requests_accepted_count +
                DailyStats.stories_viewed_count +
                DailyStats.like_friends_feed_count +
                DailyStats.friends_removed_count
            ).label("total_actions")
        )
        .where(
            DailyStats.user_id == current_user.id,
            DailyStats.date.between(start_date, end_date)
        )
        .order_by(DailyStats.date)
    )

    result = await db.execute(stmt)
    data = result.all()

    response_data = [
        ActionSummaryItem(date=row.date, total_actions=row.total_actions)
        for row in data
    ]

    return ActionSummaryResponse(data=response_data)
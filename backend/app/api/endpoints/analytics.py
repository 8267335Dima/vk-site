# --- START OF FILE backend/app/api/endpoints/analytics.py ---

import datetime
from unittest.mock import AsyncMock
from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from httpx import AsyncClient
import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, ProfileMetric, FriendRequestLog, PostActivityHeatmap
from app.api.dependencies import get_current_active_profile
from app.db.session import get_db
from app.api.schemas.analytics import (
    AudienceAnalyticsResponse, ProfileGrowthResponse, ProfileGrowthItem,
    ProfileSummaryResponse, FriendRequestConversionResponse, PostActivityHeatmapResponse,
    ProfileSummaryData
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
    try:
        return await service.get_audience_distribution()
    finally:
        if service.vk_api:
            await service.vk_api.close()

@router.get("/profile-summary", response_model=ProfileSummaryResponse)
@cache(expire=3600)
async def get_profile_summary(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """
    Возвращает текущие метрики профиля и динамику их изменения
    за последний день и неделю.
    """
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    week_ago = today - datetime.timedelta(days=7)

    stmt = select(ProfileMetric).where(
        ProfileMetric.user_id == current_user.id,
        ProfileMetric.date.in_([today, yesterday, week_ago])
    )
    result = await db.execute(stmt)
    metrics = {metric.date: metric for metric in result.scalars().all()}

    today_metrics = metrics.get(today)
    yesterday_metrics = metrics.get(yesterday)
    week_ago_metrics = metrics.get(week_ago)

    # ИСПРАВЛЕНИЕ: Безопасное создание DTO с явным маппингом полей
    if today_metrics:
        current_stats = ProfileSummaryData(
            friends=today_metrics.friends_count,
            followers=today_metrics.followers_count,
            photos=today_metrics.photos_count,
            wall_posts=today_metrics.wall_posts_count,
            recent_post_likes=today_metrics.recent_post_likes,
            recent_photo_likes=today_metrics.recent_photo_likes,
            total_post_likes=today_metrics.total_post_likes,
            total_photo_likes=today_metrics.total_photo_likes
        )
    else:
        current_stats = ProfileSummaryData()

    growth_daily = {}
    growth_weekly = {}
    
    # Используем поля схемы для итерации, чтобы ничего не пропустить
    fields_to_compare = ProfileSummaryData.model_fields.keys()
    model_field_map = {
        "friends": "friends_count", "followers": "followers_count", "photos": "photos_count",
        "wall_posts": "wall_posts_count",
        "recent_post_likes": "recent_post_likes",
        "recent_photo_likes": "recent_photo_likes",
        "total_post_likes": "total_post_likes",
        "total_photo_likes": "total_photo_likes",
    }

    for schema_field in fields_to_compare:
        model_field = model_field_map[schema_field]
        today_val = getattr(today_metrics, model_field, 0) if today_metrics else 0
        
        yesterday_val = getattr(yesterday_metrics, model_field, 0) if yesterday_metrics else 0
        growth_daily[schema_field] = today_val - yesterday_val
            
        week_ago_val = getattr(week_ago_metrics, model_field, 0) if week_ago_metrics else 0
        growth_weekly[schema_field] = today_val - week_ago_val

    return ProfileSummaryResponse(
        current_stats=current_stats,
        growth_daily=growth_daily,
        growth_weekly=growth_weekly
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
    
    # Используем ProfileGrowthItem для валидации и формирования ответа
    response_data = [ProfileGrowthItem(**row.__dict__) for row in data]

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
    
    conversion_rate = (accepted_total / sent_total * 100) if sent_total > 0 else 0.0

    return FriendRequestConversionResponse(
        sent_total=sent_total,
        accepted_total=accepted_total,
        conversion_rate=round(conversion_rate, 2)
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
        # Возвращаем пустую сетку, если данных еще нет
        return PostActivityHeatmapResponse(data=[[0]*24]*7)
        
    return PostActivityHeatmapResponse(data=heatmap_data.heatmap_data.get("data", [[0]*24]*7))

@pytest.mark.parametrize(
    "mock_friends_list",
    [
        # Случай 1: У друга нет ключа 'city'
        [{"id": 1, "sex": 1, "bdate": "1.1.2000"}],
        # Случай 2: У друга нет ключа 'bdate'
        [{"id": 2, "sex": 2, "city": {"title": "Москва"}}],
        # Случай 3: Друг деактивирован ("собачка")
        [{"id": 3, "deactivated": "deleted"}],
        # Случай 4: Пустой список друзей
        [],
    ]
)
async def test_get_audience_analytics_robustness(
    async_client: AsyncClient, auth_headers: dict, mocker, mock_friends_list
):
    """
    Тест проверяет, что эндпоинт /analytics/audience не падает с ошибкой 500,
    если VK API возвращает друзей с неполными данными.
    """
    # Arrange: Мокаем сервис, который вызывается внутри эндпоинта
    mock_service_class = mocker.patch('app.api.endpoints.analytics.AnalyticsService')
    mock_instance = mock_service_class.return_value
    
    # Мокаем метод, который делает реальную работу, чтобы он вернул нужный нам результат
    # В данном случае, мы можем просто замокать его так, чтобы он не делал ничего,
    # а сам эндпоинт протестировать, или полностью замокать его ответ.
    # Давайте протестируем сам сервис.
    mock_vk_api = AsyncMock()
    mock_vk_api.get_user_friends.return_value = mock_friends_list
    
    # "Внедряем" мок VK API в реальный экземпляр сервиса
    mocker.patch('app.services.analytics_service.AnalyticsService._initialize_vk_api', new_callable=AsyncMock)
    
    # Act
    # Мы не можем напрямую вызвать эндпоинт и одновременно мокать сервис внутри него так просто.
    # Поэтому мы протестируем сам сервис, который является ядром логики эндпоинта.
    from app.services.analytics_service import AnalyticsService
    from app.db.session import get_db
    
    async for db_session in get_db(): # Получаем сессию для инициализации
        service = AnalyticsService(db=db_session, user=await db_session.get(User, 1), emitter=AsyncMock())
        service.vk_api = mock_vk_api # Внедряем мок
        
        # Вызываем метод и ожидаем, что он не вызовет исключений
        try:
            response_model = await service.get_audience_distribution()
            # Проверяем, что модель создана корректно
            assert isinstance(response_model, dict) # get_audience_distribution вернет словарь
            assert "city_distribution" in response_model
        except Exception as e:
            pytest.fail(f"Сервис упал на неполных данных от VK: {e}")
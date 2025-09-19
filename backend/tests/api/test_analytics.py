# backend/tests/api/test_analytics.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

from app.db.models import User, ProfileMetric, FriendRequestLog, PostActivityHeatmap
from app.core.enums import FriendRequestStatus

pytestmark = pytest.mark.anyio


async def test_get_profile_summary_with_growth(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест: Проверяет эндпоинт сводки профиля, включая расчет дневного и недельного прироста.
    """
    today = date.today()
    db_session.add_all([
        ProfileMetric(user_id=test_user.id, date=today, friends_count=155, total_post_likes=1000),
        ProfileMetric(user_id=test_user.id, date=today - timedelta(days=1), friends_count=150, total_post_likes=980),
        ProfileMetric(user_id=test_user.id, date=today - timedelta(days=7), friends_count=140, total_post_likes=900),
    ])
    await db_session.commit()

    response = await async_client.get("/api/v1/analytics/profile-summary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    
    assert data["current_stats"]["friends"] == 155
    assert data["growth_daily"]["friends"] == 5
    assert data["growth_daily"]["total_post_likes"] == 20
    assert data["growth_weekly"]["friends"] == 15
    assert data["growth_weekly"]["total_post_likes"] == 100


async def test_get_profile_growth_analytics(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """
    Тест: Проверяет эндпоинт, возвращающий данные для построения графиков.
    """
    today = date.today()
    metric1 = ProfileMetric(user_id=test_user.id, date=today - timedelta(days=1), friends_count=50, total_photo_likes=500)
    metric2 = ProfileMetric(user_id=test_user.id, date=today, friends_count=52, total_photo_likes=510)
    db_session.add_all([metric1, metric2])
    await db_session.commit()

    response = await async_client.get("/api/v1/analytics/profile-growth?days=7", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    assert data[1]["friends_count"] == 52
    assert data[1]["total_photo_likes"] == 510


async def test_get_friend_request_conversion_stats(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """Тест статистики по конверсии заявок в друзья."""
    requests = []
    for i in range(10):
        status = FriendRequestStatus.accepted if i < 4 else FriendRequestStatus.pending
        requests.append(FriendRequestLog(user_id=test_user.id, target_vk_id=100 + i, status=status))
    db_session.add_all(requests)
    await db_session.commit()

    response = await async_client.get("/api/v1/analytics/friend-request-conversion", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["sent_total"] == 10
    assert data["accepted_total"] == 4
    assert data["conversion_rate"] == 40.0


async def test_get_post_activity_heatmap(async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession):
    """Тест получения данных для тепловой карты активности."""
    heatmap_data = {"data": [[10, 20], [30, 40]]} 
    heatmap = PostActivityHeatmap(user_id=test_user.id, heatmap_data=heatmap_data)
    db_session.add(heatmap)
    await db_session.commit()

    response = await async_client.get("/api/v1/analytics/post-activity-heatmap", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["data"] == heatmap_data["data"]
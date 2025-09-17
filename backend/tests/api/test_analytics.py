# --- START OF FILE tests/api/test_analytics.py ---

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
from datetime import datetime, date, timedelta, UTC

from app.db.models import User, ProfileMetric, FriendRequestLog, FriendRequestStatus, PostActivityHeatmap
from app.tasks.logic.analytics_jobs import _snapshot_all_users_metrics_async

pytestmark = pytest.mark.anyio


async def test_get_profile_summary_with_growth(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест: Проверяет эндпоинт сводки профиля, включая расчет дневного и недельного прироста.
    
    Что делает:
    1. Создает в БД метрики за сегодня, вчера и неделю назад с разными показателями.
    2. Вызывает эндпоинт /api/v1/analytics/profile-summary.
    
    Что проверяет:
    - Что API возвращает корректные текущие значения.
    - Что API правильно рассчитывает разницу (прирост) за день и за неделю.
    """
    today = date.today()
    db_session.add_all([
        # ИСПРАВЛЕНИЕ: Используем правильные имена полей
        ProfileMetric(user_id=test_user.id, date=today, friends_count=155, total_post_likes=1000, recent_post_likes=50),
        ProfileMetric(user_id=test_user.id, date=today - timedelta(days=1), friends_count=150, total_post_likes=980, recent_post_likes=45),
        ProfileMetric(user_id=test_user.id, date=today - timedelta(days=7), friends_count=140, total_post_likes=900, recent_post_likes=40),
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
    
    Что делает:
    1. Создает в БД две записи метрик за последовательные дни.
    2. Вызывает эндпоинт /api/v1/analytics/profile-growth.

    Что проверяет:
    - Что API возвращает правильное количество записей.
    - Что данные в ответе соответствуют сохраненным в БД.
    """
    today = date.today()
    # ИСПРАВЛЕНИЕ: Используем правильные имена полей
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


@patch('app.services.base.VKAPI')
async def test_snapshot_uses_user_custom_settings(
    MockVKAPI, db_session: AsyncSession, test_user: User
):
    """
    Тест: Проверяет, что фоновая задача использует персональные настройки пользователя.
    
    Что делает:
    1. Устанавливает пользователю кастомные настройки для анализа (55 постов).
    2. Мокает VK API так, чтобы он вернул 80 постов.
    3. Запускает логику фоновой задачи сбора метрик.
    
    Что проверяет:
    - Что в БД в поле `recent_post_likes` сохранилась сумма лайков именно с 55 постов.
    - Что в БД в поле `total_post_likes` сохранилась сумма лайков со всех 80 постов.
    """
    # Arrange: Задаем пользователю кастомные настройки
    test_user.analytics_settings_posts_count = 55
    test_user.analytics_settings_photos_count = 155
    await db_session.commit()

    mock_api = MockVKAPI.return_value
    
    # ИСПРАВЛЕНИЕ: Все моки асинхронных методов должны быть AsyncMock
    mock_api.users.get = AsyncMock(return_value=[{"counters": {"photos": 0}}])
    
    # ИСПРАВЛЕНИЕ: side_effect для имитации нескольких вызовов wall.get
    mock_api.wall.get = AsyncMock(side_effect=[
        # Первый вызов в _get_likes_from_wall для получения общего числа
        {"count": 80},
        # Второй вызов в _get_likes_from_wall для получения первого чанка постов
        {"items": [{"likes": {"count": 1}} for _ in range(80)]}
    ])
    
    mock_api.photos.getAll = AsyncMock(return_value={"count": 0, "items": []})
    mock_api.close = AsyncMock()
    
    # Act: Запускаем логику сбора метрик
    await _snapshot_all_users_metrics_async(session_for_test=db_session)

    # Assert: Проверяем результат в БД
    await db_session.flush() # Гарантируем, что сессия видит изменения
    metric = await db_session.get(ProfileMetric, 1)
    
    assert metric is not None
    # Сервис должен был посчитать лайки для 55 постов (как в настройках)
    assert metric.recent_post_likes == 55
    # Общее количество лайков должно быть со всех 80 постов
    assert metric.total_post_likes == 80


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

# --- END OF FILE tests/api/test_analytics.py ---
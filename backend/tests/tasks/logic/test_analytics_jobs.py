# backend/tests/tasks/logic/test_analytics_jobs.py

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from app.db.models import User, ProfileMetric, FriendRequestLog
from app.core.enums import FriendRequestStatus
from app.db.models import Plan # Добавьте эту строку
from app.core.enums import PlanName # Добавьте эту строку
from sqlalchemy import select # Добавьте эту строку
from app.tasks.profile_parser import _snapshot_all_users_metrics_async
# А _update... остается в analytics_jobs.py
from app.tasks.logic.analytics_jobs import _update_friend_request_statuses_async


pytestmark = pytest.mark.anyio


@patch('app.services.base.VKAPI')
async def test_snapshot_uses_user_custom_settings(
    MockVKAPI, db_session: AsyncSession, test_user: User
):
    """
    Тест: Проверяет, что фоновая задача использует персональные настройки пользователя.
    """
    # Arrange
    test_user.analytics_settings_posts_count = 55
    await db_session.commit()

    mock_api = MockVKAPI.return_value
    mock_api.users.get = AsyncMock(return_value=[{"counters": {"photos": 0}}])
    mock_api.wall.get = AsyncMock(side_effect=[
        {"count": 80},
        {"items": [{"likes": {"count": 1}} for _ in range(80)]}
    ])
    mock_api.photos.getAll = AsyncMock(return_value={"count": 0, "items": []})
    mock_api.close = AsyncMock()
    
    # Act: Вызываем _snapshot_all_users_metrics_async, который теперь импортирован правильно
    await _snapshot_all_users_metrics_async(session=db_session)

    # Assert
    metric = await db_session.get(ProfileMetric, 1)
    
    assert metric is not None
    assert metric.recent_post_likes == 55
    assert metric.total_post_likes == 80


@patch('app.tasks.logic.analytics_jobs.VKAPI')
@patch('app.tasks.logic.analytics_jobs.decrypt_data')
async def test_update_friend_requests_logic(
    mock_decrypt, MockVKAPI, db_session: AsyncSession
):
    """
    Тест: Проверяет логику обновления статусов заявок в друзья.
    """
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()

    invalid_user = User(vk_id=111, encrypted_vk_token="invalid_token", plan_id=pro_plan.id)
    req1 = FriendRequestLog(user=invalid_user, target_vk_id=1, status=FriendRequestStatus.pending)
    valid_user = User(vk_id=222, encrypted_vk_token="valid_token", plan_id=pro_plan.id)
    req2 = FriendRequestLog(user=valid_user, target_vk_id=2, status=FriendRequestStatus.pending)
    db_session.add_all([invalid_user, valid_user, req1, req2])
    await db_session.commit()

    def fake_decrypt(token):
        return "vk_token" if token == "valid_token" else None
    mock_decrypt.side_effect = fake_decrypt

    mock_api = MockVKAPI.return_value
    # Делаем метод асинхронным и сразу задаем возвращаемое значение
    mock_api.get_user_friends = AsyncMock(return_value={"items": [2, 3, 4]})
    mock_api.close = AsyncMock()

    # Act: Вызываем _update_friend_request_statuses_async
    await _update_friend_request_statuses_async(session=db_session)

    # Assert
    await db_session.refresh(req1)
    await db_session.refresh(req2)
    assert req1.status == FriendRequestStatus.pending
    assert req2.status == FriendRequestStatus.accepted
# tests/services/test_feed_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from unittest.mock import AsyncMock

from app.services.feed_service import FeedService
from app.services.humanizer import Humanizer # <-- Добавьте этот импорт
from app.db.models import User, DailyStats
from app.api.schemas.actions import LikeFeedRequest, ActionFilters
from app.services.event_emitter import RedisEventEmitter

pytestmark = pytest.mark.anyio


async def test_like_newsfeed_service_success(
    db_session: AsyncSession, test_user: User, mock_emitter: RedisEventEmitter, mocker
):
    """
    Тестирует логику FeedService в изоляции.
    """
    service = FeedService(db=db_session, user=test_user, emitter=mock_emitter)

    mock_humanizer = AsyncMock(spec=Humanizer)
    service.humanizer = mock_humanizer
    
    # Мокаем VK API
    mock_vk_api = AsyncMock()
    mock_vk_api.newsfeed.get.return_value = {
        "items": [
            {"type": "post", "source_id": 123, "post_id": 1, "likes": {"user_likes": 0}},
            {"type": "post", "source_id": 456, "post_id": 2, "likes": {"user_likes": 0}},
        ]
    }
    # Мокаем метод users.get, который вызывается внутри _get_user_profiles
    mock_vk_api.users.get.return_value = [{"id": 123}, {"id": 456}]
    mock_vk_api.likes.add.return_value = {"likes": 1}
    service.vk_api = mock_vk_api
    
    request_params = LikeFeedRequest(count=2, filters=ActionFilters())
    await service._like_newsfeed_logic(request_params)

    assert mock_vk_api.likes.add.call_count == 2
    
    mock_emitter.send_log.assert_any_call(
        "Задача завершена. Поставлено лайков: 2.", "success"
    )

    stats = (await db_session.execute(
        select(DailyStats).where(DailyStats.user_id == test_user.id)
    )).scalar_one()
    assert stats.likes_count == 2
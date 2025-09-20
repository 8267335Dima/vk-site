# tests/services/test_ai_and_filters.py

import pytest
from datetime import datetime, timedelta, timezone

from app.services.ai_message_service import AIMessageService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import ActionFilters

pytestmark = pytest.mark.anyio

# ---- Тесты для AIMessageService ----

class TestAIMessageServiceContextBuilding:

    def test_build_context_with_text_and_photo(self):
        """Проверяет, что сообщение с текстом и фото правильно преобразуется в сложный 'content'."""
        service = AIMessageService(db=None, user=None, emitter=None)
        own_vk_id = 1
        messages = [
            {"from_id": 2, "text": "Смотри какая фотка", "attachments": [
                {"type": "photo", "photo": {"sizes": [{"url": "http://example.com/s.jpg", "height": 100}, {"url": "http://example.com/l.jpg", "height": 500}]}}
            ]}
        ]
        
        context = service._build_context_from_history(messages, own_vk_id)
        
        assert len(context) == 1
        content = context[0]['content']
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "Смотри какая фотка"}
        assert content[1] == {"type": "image_url", "image_url": {"url": "http://example.com/l.jpg"}}

    def test_build_context_with_sticker_and_wall(self):
        """Проверяет, что стикеры преобразуются в image_url, а репосты - в текстовое описание."""
        service = AIMessageService(db=None, user=None, emitter=None)
        own_vk_id = 1
        messages = [
            {"from_id": 2, "text": "", "attachments": [
                {"type": "sticker", "sticker": {"images": [{"url": "http://stickers.com/s.png", "height": 64}, {"url": "http://stickers.com/l.png", "height": 128}]}},
                {"type": "wall", "wall": {}}
            ]}
        ]
        
        context = service._build_context_from_history(messages, own_vk_id)
        
        assert len(context) == 1
        content = context[0]['content']
        assert content[0] == {"type": "text", "text": "[пересланное сообщение со стены]"}
        assert content[1] == {"type": "image_url", "image_url": {"url": "http://stickers.com/l.png"}}

# ---- Тесты для vk_user_filter ----

class TestVKUserFilterEdgeCases:

    @pytest.mark.asyncio
    async def test_filter_by_last_seen_hours(self):
        """Проверяет фильтр 'заходил не позднее N часов назад'."""
        now_ts = datetime.now(timezone.utc).timestamp()
        profiles = [
            {"id": 1, "last_seen": {"time": now_ts - 3600}},       # 1 час назад
            {"id": 2, "last_seen": {"time": now_ts - 10800}},      # 3 часа назад
            {"id": 3, "last_seen": {"time": now_ts - 86400}},      # 24 часа назад
            {"id": 4},                                             # Нет информации
        ]
        
        # Оставить тех, кто был онлайн в течение последних 2 часов
        filters = ActionFilters(last_seen_hours=2)
        result = await apply_filters_to_profiles(profiles, filters)
        
        assert len(result) == 1
        assert result[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_filter_by_last_seen_days(self):
        """Проверяет фильтр 'не заходил более N дней' (для удаления неактивных)."""
        now_ts = datetime.now(timezone.utc).timestamp()
        one_day = 86400
        profiles = [
            {"id": 1, "last_seen": {"time": now_ts - one_day * 5}},    # 5 дней назад
            {"id": 2, "last_seen": {"time": now_ts - one_day * 15}},   # 15 дней назад
            {"id": 3, "last_seen": {"time": now_ts - one_day * 35}},   # 35 дней назад
        ]
        
        # Оставить тех, кто НЕ был онлайн более 10 дней
        filters = ActionFilters(last_seen_days=10)
        result = await apply_filters_to_profiles(profiles, filters)
        
        assert len(result) == 2
        assert {p["id"] for p in result} == {2, 3}

    @pytest.mark.asyncio
    async def test_filter_remove_banned_logic(self):
        """Проверяет, что `remove_banned=False` исключает 'собачек' из выборки."""
        profiles = [
            {"id": 1, "deactivated": "banned"},
            {"id": 2, "first_name": "Active"},
            {"id": 3, "deactivated": "deleted"},
        ]
        
        # remove_banned=False означает, что мы НЕ ХОТИМ видеть "собачек"
        filters = ActionFilters(remove_banned=False)
        result = await apply_filters_to_profiles(profiles, filters)
        
        assert len(result) == 1
        assert result[0]['id'] == 2
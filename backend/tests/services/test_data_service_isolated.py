# tests/services/test_data_service_isolated.py

import pytest
from unittest.mock import AsyncMock
from collections import Counter

from app.services.data_service import DataService

pytestmark = pytest.mark.anyio

class TestDataServiceIsolated:

    @pytest.fixture
    def mock_vk_api(self):
        """Фикстура для создания мока VK API."""
        return AsyncMock()

    @pytest.fixture
    def data_service(self, mock_vk_api) -> DataService:
        """Фикстура для создания экземпляра DataService с моком VK API."""
        service = DataService(db=None, user=None, emitter=None)
        service.vk_api = mock_vk_api
        return service

    async def test_parse_top_active_users_logic(self, data_service: DataService, mock_vk_api: AsyncMock):
        """
        Тест логики подсчета очков активности и сортировки пользователей.
        Проверяет, что комментарии ценятся выше лайков.
        """
        # Arrange
        group_id = -123
        # Настраиваем моки ответов от VK API
        mock_vk_api.wall.get.return_value = {"items": [{"id": 1}]}
        mock_vk_api.likes.getList.return_value = {"items": [101, 102]} # User 101, 102 лайкнули
        mock_vk_api.wall.getComments.return_value = {
            "items": [
                {"from_id": 102}, # User 102 прокомментировал
                {"from_id": 103}  # User 103 прокомментировал
            ]
        }
        mock_vk_api.users.get.return_value = [
            {"id": 103, "first_name": "Самый", "last_name": "Активный"},
            {"id": 102, "first_name": "Средне", "last_name": "Активный"},
            {"id": 101, "first_name": "Мало", "last_name": "Активный"},
        ]

        # Act
        results = await data_service.parse_top_active_users(group_id, posts_depth=1, top_n=3)

        # Assert
        # Ожидаемые очки:
        # User 101: 1 (лайк)
        # User 102: 1 (лайк) + 2 (комментарий) = 3
        # User 103: 2 (комментарий)
        assert len(results) == 3
        assert results[0]["user_info"]["id"] == 102
        assert results[0]["activity_score"] == 3
        assert results[1]["user_info"]["id"] == 103
        assert results[1]["activity_score"] == 2
        assert results[2]["user_info"]["id"] == 101
        assert results[2]["activity_score"] == 1

    async def test_parse_group_activity_handles_empty_responses(self, data_service: DataService, mock_vk_api: AsyncMock):
        """Тест проверяет, что парсер активной аудитории не падает на пустых ответах."""
        # Arrange
        mock_vk_api.wall.get.return_value = {"items": [{"id": 1}]}
        mock_vk_api.likes.getList.return_value = None # Лайков нет
        mock_vk_api.wall.getComments.return_value = {"items": []} # Комментариев нет
        
        # Act
        results = await data_service.parse_active_group_audience(1, AsyncMock())

        # Assert
        assert results == []
        mock_vk_api.users.get.assert_not_called() # Проверяем, что не было лишнего запроса за профилями

    async def test_export_conversation_stream(self, data_service: DataService, mock_vk_api: AsyncMock):
        """Тест проверяет корректность JSON-стриминга при экспорте диалога."""
        # Arrange
        mock_vk_api.messages.getHistory.side_effect = [
            {"items": [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}]},
            {"items": [{"id": 3, "text": "c"}]},
            None # Конец истории
        ]

        # Act
        # Собираем все части стрима в одну строку
        json_stream_parts = [part async for part in data_service.export_conversation_as_json(123)]
        full_json_string = "".join(json_stream_parts)

        # Assert
        assert mock_vk_api.messages.getHistory.call_count == 3
        
        # Проверяем, что итоговая строка является валидным JSON-массивом из 3х объектов
        import json
        data = json.loads(full_json_string)
        assert isinstance(data, list)
        assert len(data) == 3
        assert data[2]['id'] == 3
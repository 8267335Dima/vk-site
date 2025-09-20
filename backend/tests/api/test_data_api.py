# tests/api/test_data_api.py

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

pytestmark = pytest.mark.anyio

@pytest.fixture
def mock_data_service(mocker):
    """
    Мокает DataService для изоляции тестов API. 
    Патчим класс в том модуле, где он используется (в эндпоинте).
    """
    mock_service_class = mocker.patch("app.api.endpoints.data.DataService")
    mock_instance = mock_service_class.return_value
    # Настраиваем моки для всех методов, которые будут вызываться
    mock_instance.parse_active_group_audience = AsyncMock(return_value=[{"id": 1, "first_name": "Активный"}])
    mock_instance.parse_group_members = AsyncMock(return_value=[{"id": 2, "first_name": "Подписчик"}])
    mock_instance.parse_user_wall = AsyncMock(return_value=[{"id": 101, "text": "Мой пост"}])
    mock_instance.parse_top_active_users = AsyncMock(return_value=[{"user_info": {"id": 4}, "activity_score": 10}])
    
    # Мок для стриминга
    async def mock_stream_generator(*args, **kwargs):
        yield '{"message": "hello"}'
    mock_instance.export_conversation_as_json = mock_stream_generator
    
    # Важно: мокаем __aenter__ и __aexit__ для async with
    mock_instance.vk_api = AsyncMock()
    mock_instance.vk_api.close = AsyncMock()

    return mock_instance

class TestDataApiEndpoints:

    async def test_parse_group_activity(
        self, async_client: AsyncClient, auth_headers: dict, mock_data_service: AsyncMock
    ):
        """Тест эндпоинта для парсинга активной аудитории сообщества."""
        response = await async_client.post(
            "/api/v1/data/parse/group-activity",
            headers=auth_headers,
            json={"group_id": 123, "filters": {"posts_depth": 5}}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["first_name"] == "Активный"
        mock_data_service.parse_active_group_audience.assert_awaited_once()

    async def test_parse_group_members(
        self, async_client: AsyncClient, auth_headers: dict, mock_data_service: AsyncMock
    ):
        """Тест эндпоинта для парсинга подписчиков сообщества."""
        response = await async_client.post(
            "/api/v1/data/parse/group-members",
            headers=auth_headers,
            json={"group_id": 456, "count": 100}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data[0]["first_name"] == "Подписчик"
        mock_data_service.parse_group_members.assert_awaited_once_with(456, 100)

    async def test_parse_user_wall(
        self, async_client: AsyncClient, auth_headers: dict, mock_data_service: AsyncMock
    ):
        """Тест эндпоинта для парсинга стены пользователя."""
        response = await async_client.post(
            "/api/v1/data/parse/user-wall",
            headers=auth_headers,
            json={"user_id": 789, "count": 50}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data[0]["text"] == "Мой пост"
        mock_data_service.parse_user_wall.assert_awaited_once_with(789, 50)

    async def test_parse_top_active_users(
        self, async_client: AsyncClient, auth_headers: dict, mock_data_service: AsyncMock
    ):
        """Тест эндпоинта для парсинга топа активных пользователей."""
        response = await async_client.post(
            "/api/v1/data/parse/group-top-active",
            headers=auth_headers,
            json={"group_id": 111, "posts_depth": 10, "top_n": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data[0]["activity_score"] == 10
        mock_data_service.parse_top_active_users.assert_awaited_once_with(111, 10, 5)

    async def test_export_conversation(
        self, async_client: AsyncClient, auth_headers: dict, mock_data_service: AsyncMock
    ):
        """Тест эндпоинта для экспорта переписки (проверяет сам факт вызова и статус)."""
        peer_id = 999
        response = await async_client.get(
            f"/api/v1/data/export/conversation/{peer_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        # Проверяем, что тело ответа соответствует тому, что вернул мок-генератор
        assert response.text == '{"message": "hello"}'
        # Проверяем, что был вызван правильный метод сервиса
        # assert mock_data_service.export_conversation_as_json.call_count == 1
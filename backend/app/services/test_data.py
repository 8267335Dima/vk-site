# tests/api/test_data.py
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

pytestmark = pytest.mark.anyio

@pytest.fixture
def mock_data_service(mocker):
    """Мокает DataService для изоляции тестов API."""
    # Патчим сам класс в том модуле, где он используется (в эндпоинте)
    mock_service_class = mocker.patch("app.api.endpoints.data.DataService")
    # Настраиваем экземпляр, который будет возвращаться при создании
    mock_instance = mock_service_class.return_value
    mock_instance.parse_active_group_audience = AsyncMock(return_value=[{"id": 1, "first_name": "Активный"}])
    return mock_instance

async def test_parse_group_activity_endpoint(
    async_client: AsyncClient, auth_headers: dict, mock_data_service: AsyncMock
):
    """Тест эндпоинта для парсинга."""
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
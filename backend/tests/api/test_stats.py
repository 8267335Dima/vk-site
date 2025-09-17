# tests/api/test_stats.py

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

pytestmark = pytest.mark.anyio

@pytest.mark.parametrize(
    "mock_vk_response, expected_result",
    [
        # Случай 1: VK вернул пустой ответ
        (None, {"male_count": 0, "female_count": 0, "other_count": 0}),
        # Случай 2: VK вернул ответ без ключа 'items'
        ({"count": 0}, {"male_count": 0, "female_count": 0, "other_count": 0}),
        # Случай 3: VK вернул 'items', но это не список
        ({"items": "неожиданная строка"}, {"male_count": 0, "female_count": 0, "other_count": 0}),
        # Случай 4: У друга нет ключа 'sex'
        ({"items": [{"id": 1, "first_name": "Test"}]}, {"male_count": 0, "female_count": 0, "other_count": 1}),
    ]
)
async def test_friends_analytics_robustness(
    async_client: AsyncClient, auth_headers: dict, mocker, mock_vk_response, expected_result
):
    """
    Тест проверяет, что эндпоинт /friends-analytics корректно обрабатывает
    неожиданные или неполные ответы от VK API, не вызывая 500 ошибку.
    """
    # Arrange
    # Мокаем класс VKAPI в том месте, где он используется
    mock_vk_api_class = mocker.patch('app.api.endpoints.stats.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    
    # Настраиваем мок-методы
    mock_instance.get_user_friends = AsyncMock(return_value=mock_vk_response)
    mock_instance.close = AsyncMock()

    # Act
    response = await async_client.get("/api/v1/stats/friends-analytics", headers=auth_headers)

    # Assert
    assert response.status_code == 200
    assert response.json() == expected_result
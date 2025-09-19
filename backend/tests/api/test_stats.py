# tests/api/test_stats.py

import pytest
from unittest.mock import AsyncMock

# 1. Инициализируем кеш, так как тестируемая функция им декорирована.
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
FastAPICache.init(InMemoryBackend())

# 2. Импортируем тестируемую функцию и модель напрямую для юнит-теста
from app.api.endpoints.stats import get_friends_analytics
from app.db.models import User

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "mock_vk_response, expected_result",
    [
        (None, {"male_count": 0, "female_count": 0, "other_count": 0}),
        ({"count": 0, "items": []}, {"male_count": 0, "female_count": 0, "other_count": 0}),
        ({"items": "некорректная строка"}, {"male_count": 0, "female_count": 0, "other_count": 0}),
        ({"items": [{"id": 1, "first_name": "Test"}]}, {"male_count": 0, "female_count": 0, "other_count": 1}),
        ({"items": [{"sex": 1}, {"sex": 2}, {"sex": 2}]}, {"male_count": 2, "female_count": 1, "other_count": 0}),
    ]
)
async def test_friends_analytics_logic(
    test_user: User, mocker, mock_vk_response, expected_result
):
    """
    Юнит-тест, который проверяет исключительно логику подсчета
    внутри эндпоинта /friends-analytics, вызывая функцию напрямую.
    """
    # Arrange: Настраиваем мок VK API
    mock_vk_api_class = mocker.patch('app.api.endpoints.stats.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    mock_instance.get_user_friends = AsyncMock(return_value=mock_vk_response)
    mock_instance.close = AsyncMock()

    # Act: Вызываем саму функцию
    result = await get_friends_analytics(current_user=test_user)

    # Assert: Сравниваем результат (словарь) с ожидаемым словарем
    assert result == expected_result
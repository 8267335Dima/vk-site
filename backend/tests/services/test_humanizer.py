# tests/services/test_humanizer.py

import pytest
from unittest.mock import AsyncMock, call

from app.services.humanizer import Humanizer
from app.db.models import DelayProfile
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.asyncio

@patch('app.services.humanizer.asyncio.sleep', new_callable=AsyncMock)
async def test_humanizer_delay_profiles(mock_sleep: AsyncMock):
    """
    Unit-тест проверяет, что Humanizer с профилем 'slow' запрашивает
    бОльшую задержку, чем Humanizer с профилем 'fast'.
    """
    # Arrange
    mock_logger = AsyncMock()
    
    # Создаем два экземпляра с разными профилями
    humanizer_fast = Humanizer(delay_profile=DelayProfile.fast, logger_func=mock_logger)
    humanizer_slow = Humanizer(delay_profile=DelayProfile.slow, logger_func=mock_logger)
    
    # Act
    # Вызываем одно и то же действие для обоих
    await humanizer_fast.think(action_type='like')
    await humanizer_slow.think(action_type='like')

    # Assert
    # Получаем аргументы, с которыми был вызван asyncio.sleep
    fast_sleep_call = mock_sleep.call_args_list[0]
    slow_sleep_call = mock_sleep.call_args_list[1]
    
    fast_delay_duration = fast_sleep_call.args[0]
    slow_delay_duration = slow_sleep_call.args[0]

    print(f"Fast delay: {fast_delay_duration}, Slow delay: {slow_delay_duration}")

    # Ключевая проверка: "медленный" профиль должен ждать дольше "быстрого"
    assert slow_delay_duration > fast_delay_duration
# tests/services/test_message_humanizer_robustness.py

import pytest
from unittest.mock import AsyncMock
import asyncio

from app.services.message_humanizer import MessageHumanizer
from app.services.vk_api import VKAPI, VKAPIError

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_vk_api(mocker):
    api = mocker.MagicMock(spec=VKAPI)
    api.messages = AsyncMock()
    return api

@pytest.fixture
def mock_emitter(mocker):
    emitter = mocker.MagicMock()
    emitter.send_log = AsyncMock()
    # Добавляем user_id для совместимости с логгером внутри сервиса
    emitter.user_id = 123 
    return emitter

async def test_humanizer_continues_after_generic_vk_api_error(mock_vk_api, mock_emitter, mocker):
    """
    Тест на отказоустойчивость: MessageHumanizer должен продолжить рассылку,
    даже если на одном из пользователей VK API вернул непредвиденную ошибку.
    """
    # Arrange
    mocker.patch('asyncio.sleep', new_callable=AsyncMock)
    targets = [
        {"id": 1, "first_name": "Успешный"},
        {"id": 2, "first_name": "Ошибка"},
        {"id": 3, "first_name": "Снова Успешный"}
    ]
    
    # Настраиваем мок VK API: на втором вызове он выбрасывает VKAPIError
    mock_vk_api.messages.send.side_effect = [
        1, # Успех для id=1
        VKAPIError("Something bad happened", 100), # Ошибка для id=2
        1  # Успех для id=3
    ]
    humanizer = MessageHumanizer(vk_api=mock_vk_api, emitter=mock_emitter)

    # Act
    sent_count = await humanizer.send_messages_sequentially(
        targets=targets, message_template="Привет", simulate_typing=False
    )

    # Assert
    assert sent_count == 2 # Должно быть 2 успешных отправки
    assert mock_vk_api.messages.send.await_count == 3 # Метод send был вызван 3 раза
    
    # Проверяем, что была залогирована именно ошибка, а не предупреждение
    mock_emitter.send_log.assert_any_call(
        "Ошибка при отправке сообщения для Ошибка : VK API Error [100]: Something bad happened", 
        "error", 
        target_url="https://vk.com/id2"
    )
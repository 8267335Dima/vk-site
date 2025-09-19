# tests/services/test_message_humanizer.py

import pytest
from unittest.mock import AsyncMock, call
import asyncio

from app.services.message_humanizer import MessageHumanizer
from app.services.vk_api import VKAPI, VKAccessDeniedError

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_vk_api(mocker):
    """Фикстура для мокирования VK API."""
    api = mocker.MagicMock(spec=VKAPI)
    api.messages.setActivity = AsyncMock()
    api.messages.send = AsyncMock(return_value=12345) # Успешная отправка
    return api

@pytest.fixture
def mock_emitter(mocker):
    """Фикстура для мокирования эмиттера."""
    emitter = mocker.MagicMock()
    emitter.send_log = AsyncMock()
    return emitter

async def test_humanizer_simulates_typing_and_sends(mock_vk_api, mock_emitter, mocker):
    """
    Тест проверяет, что 'очеловечиватель' вызывает setActivity (имитация набора),
    выдерживает паузу и затем отправляет сообщение.
    """
    # Arrange
    mocker.patch('asyncio.sleep', new_callable=AsyncMock) # Мокаем asyncio.sleep
    humanizer = MessageHumanizer(vk_api=mock_vk_api, emitter=mock_emitter)
    target = [{"id": 123, "first_name": "Тест"}]
    message = "Это тестовое сообщение"
    
    # Act
    sent_count = await humanizer.send_messages_sequentially(
        targets=target,
        message_template=message,
        speed="fast",
        simulate_typing=True
    )

    # Assert
    assert sent_count == 1
    # Проверяем, что был вызван метод для показа "набирает сообщение"
    mock_vk_api.messages.setActivity.assert_awaited_once_with(user_id=123, type='typing')
    # Проверяем, что после этого было отправлено само сообщение
    mock_vk_api.messages.send.assert_awaited_once_with(123, message, attachment=None)
    # Проверяем, что были вызовы sleep (для пауз)
    asyncio.sleep.assert_called()

async def test_humanizer_handles_access_denied_gracefully(mock_vk_api, mock_emitter, mocker):
    """
    Тест проверяет, что если VK API возвращает ошибку доступа (профиль закрыт, ЧС),
    'очеловечиватель' не падает, а логирует это и продолжает работу.
    """
    # Arrange
    mocker.patch('asyncio.sleep', new_callable=AsyncMock)
    # Первый получатель доступен, второй - нет
    targets = [
        {"id": 1, "first_name": "Успешный"},
        {"id": 2, "first_name": "Закрытый"},
        {"id": 3, "first_name": "Еще_Успешный"}
    ]
    # Настраиваем мок VK API так, чтобы на втором вызове он выбрасывал ошибку
    mock_vk_api.messages.send.side_effect = [
        1, # Успех для id=1
        VKAccessDeniedError("Permission denied", 15), # Ошибка для id=2
        1  # Успех для id=3
    ]
    humanizer = MessageHumanizer(vk_api=mock_vk_api, emitter=mock_emitter)

    # Act
    sent_count = await humanizer.send_messages_sequentially(
        targets=targets, message_template="Привет", simulate_typing=False
    )

    # Assert
    # Должно быть 2 успешных отправки
    assert sent_count == 2
    # Метод send должен был быть вызван 3 раза
    assert mock_vk_api.messages.send.await_count == 3
    # Проверяем, что было залогировано предупреждение
    mock_emitter.send_log.assert_any_call(
        "Не удалось отправить (профиль закрыт или ЧС): Закрытый ", "warning", target_url="https://vk.com/id2"
    )
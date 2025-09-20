# tests/services/test_ai_service.py
import pytest
from unittest.mock import AsyncMock, patch

from app.services.ai_message_service import AIMessageService
from app.db.models import User

pytestmark = pytest.mark.asyncio

@patch('app.services.ai_message_service.UnifiedAIService')
async def test_ai_message_service_processes_conversation(
    MockUnifiedAIService, db_session, test_user: User, mock_emitter # <--- Аргумент переименован для ясности
):
    """
    Тест проверяет, что AI-сервис правильно обрабатывает один диалог:
    получает историю, вызывает ИИ и отправляет ответ.
    """
    # Arrange
    # Мокаем UnifiedAIService
    mock_ai_instance = MockUnifiedAIService.return_value
    mock_ai_instance.get_response = AsyncMock(return_value="Сгенерированный ответ")

    # Мокаем VK API
    mock_vk_api = AsyncMock()
    # 1. Возвращаем один непрочитанный диалог
    mock_vk_api.messages.getConversations.return_value = {
        "items": [{"conversation": {"peer": {"id": 123}}}]
    }
    # 2. Возвращаем историю для этого диалога
    mock_vk_api.messages.getHistory.return_value = {
        "items": [
            {"from_id": 123, "text": "Привет, бот!"}, # последнее от пользователя
            {"from_id": test_user.vk_id, "text": "Здравствуйте!"} # наш предыдущий ответ
        ]
    }
    mock_vk_api.messages.send = AsyncMock(return_value=1)
    
    # Мокаем humanizer, чтобы не ждать sleep
    mock_humanizer_class = patch('app.services.ai_message_service.MessageHumanizer').start()
    mock_humanizer_instance = mock_humanizer_class.return_value
    mock_humanizer_instance.send_messages_sequentially = AsyncMock()

    service = AIMessageService(db=db_session, user=test_user, emitter=mock_emitter)
    service.vk_api = mock_vk_api
    
    # Act
    await service.process_unanswered_conversations(params={'count': 10})

    # Assert
    # 1. Проверяем, что ИИ был вызван с правильным контекстом
    mock_ai_instance.get_response.assert_awaited_once()
    call_args, call_kwargs = mock_ai_instance.get_response.call_args
    assert call_kwargs['user_input'] == "Привет, бот!"
    assert len(call_kwargs['message_history']) == 1
    assert call_kwargs['message_history'][0]['content'] == "Здравствуйте!"
    
    # 2. Проверяем, что 'очеловечиватель' был вызван для отправки ответа
    mock_humanizer_instance.send_messages_sequentially.assert_awaited_once_with(
        targets=[{'id': 123}],
        message_template="Сгенерированный ответ",
        speed="normal",
        simulate_typing=True
    )
    
    # Останавливаем патч
    patch.stopall()
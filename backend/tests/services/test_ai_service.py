# tests/services/test_ai_service.py
import pytest
from unittest.mock import AsyncMock, patch

from app.services.ai_message_service import AIMessageService
from app.db.models import User
from app.core.security import encrypt_data

pytestmark = pytest.mark.asyncio

@patch('app.services.ai_message_service.UnifiedAIService')
async def test_ai_message_service_processes_conversation(
    MockUnifiedAIService, db_session, test_user: User, mock_emitter
):
    """
    Тест проверяет, что AI-сервис правильно обрабатывает один диалог:
    получает историю, вызывает ИИ и отправляет ответ.
    """
    # Arrange
    test_user.ai_provider = "google"
    test_user.encrypted_ai_api_key = encrypt_data("fake_key") # encrypt_data импортируется из app.core.security
    test_user.ai_model_name = "gemini-pro"
    await db_session.commit()

    mock_ai_instance = MockUnifiedAIService.return_value
    mock_ai_instance.get_response = AsyncMock(return_value="Сгенерированный ответ")

    mock_vk_api = AsyncMock()
    mock_vk_api.messages.getConversations.return_value = {
        "items": [{"conversation": {"peer": {"id": 123}}}]
    }
    mock_vk_api.messages.getHistory.return_value = {
        "items": [
            {"from_id": 123, "text": "Привет, бот!"},
            {"from_id": test_user.vk_id, "text": "Здравствуйте!"}
        ]
    }
    mock_vk_api.messages.send = AsyncMock(return_value=1)
    
    mock_humanizer_class = patch('app.services.ai_message_service.MessageHumanizer').start()
    mock_humanizer_instance = mock_humanizer_class.return_value
    mock_humanizer_instance.send_messages_sequentially = AsyncMock()

    service = AIMessageService(db=db_session, user=test_user, emitter=mock_emitter)
    service.vk_api = mock_vk_api
    
    # Act
    await service.process_unanswered_conversations(params={'count': 10})

    # Assert
    mock_ai_instance.get_response.assert_awaited_once()
    call_args, call_kwargs = mock_ai_instance.get_response.call_args
    assert call_kwargs['user_input'] == "Привет, бот!"
    
    mock_humanizer_instance.send_messages_sequentially.assert_awaited_once_with(
        targets=[{'id': 123}],
        message_template="Сгенерированный ответ",
        speed="normal",
        simulate_typing=True
    )
    
    patch.stopall()
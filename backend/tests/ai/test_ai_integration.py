# tests/ai/test_ai_integration.py

import pytest
from httpx import AsyncClient, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch, MagicMock
from openai import APIError, RateLimitError

from app.db.models import User
from app.core.security import decrypt_data
from app.ai.unified_service import UnifiedAIService

pytestmark = pytest.mark.anyio

# ИСПРАВЛЕНО: Создаем мок request и передаем его в response для RateLimitError
@pytest.mark.parametrize("error_to_raise", [
    APIError(message="Test API Error", request=Request(method="POST", url="http://test"), body=None),
    RateLimitError(
        message="Rate limit exceeded", 
        response=Response(429, request=Request(method="POST", url="http://test")), 
        body=None
    ),
    Exception("Unknown generic error")
])
@patch('app.ai.unified_service.AsyncOpenAI')
async def test_ai_service_fallback_on_errors(MockAsyncOpenAI, error_to_raise):
    """
    Юнит-тест: проверяет, что UnifiedAIService возвращает сообщение-заглушку
    при любых ошибках от OpenAI-совместимого клиента, а не падает.
    """
    # Arrange
    mock_client_instance = MockAsyncOpenAI.return_value
    mock_client_instance.chat.completions.create.side_effect = error_to_raise

    fallback_message = "Извините, ИИ сейчас недоступен."
    service = UnifiedAIService(
        provider="openai",
        api_key="fake_key",
        model="gpt-4",
        fallback_message=fallback_message
    )

    # Act
    response = await service.get_response("system prompt", [], "user input")

    # Assert
    assert response == fallback_message

# Остальные тесты в этом файле остаются без изменений, так как они уже корректны.
@patch('app.ai.unified_service.AsyncOpenAI')
async def test_ai_service_sends_images_correctly(MockAsyncOpenAI):
    """
    НОВЫЙ ТЕСТ: Проверяет, что сервис правильно формирует 'content'
    при передаче текста и изображений.
    """
    # Arrange
    mock_completion = AsyncMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="Image received"))]
    mock_client_instance = MockAsyncOpenAI.return_value
    mock_client_instance.chat.completions.create.return_value = mock_completion
    
    service = UnifiedAIService("openai", "fake_key", "gpt-4-vision", "fallback")
    
    images_to_send = [
        "http://example.com/image1.jpg",
        {"url": "http://example.com/image2.png"},
        {"data": "base64_encoded_string", "format": "jpeg"}
    ]
    
    # Act
    await service.get_response("system", [], "user input", images=images_to_send)
    
    # Assert
    mock_client_instance.chat.completions.create.assert_awaited_once()
    _, kwargs = mock_client_instance.chat.completions.create.call_args
    messages = kwargs['messages']
    user_message_content = messages[-1]['content']
    
    assert isinstance(user_message_content, list)
    assert len(user_message_content) == 4 # 1 текст + 3 изображения
    assert user_message_content[0] == {"type": "text", "text": "user input"}
    assert user_message_content[1]["image_url"]["url"] == "http://example.com/image1.jpg"
    assert user_message_content[2]["image_url"]["url"] == "http://example.com/image2.png"
    assert user_message_content[3]["image_url"]["url"] == "data:image/jpeg;base64,base64_encoded_string"

async def test_update_and_get_ai_settings_e2e(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User
):
    """E2E-тест: проверяет полный цикл CRUD для настроек ИИ через API."""
    # 1. Update settings
    update_data = {
        "provider": "google",
        "api_key": "test_gemini_api_key_12345",
        "model_name": "gemini-2.5-pro",
        "system_prompt": "You are a test bot.",
        "ai_fallback_message": "Бот временно отдыхает."
    }
    response_update = await async_client.put("/api/v1/ai/settings", headers=auth_headers, json=update_data)
    
    assert response_update.status_code == 200
    data_update = response_update.json()
    assert data_update["provider"] == "google"
    assert data_update["is_configured"] is True
    assert data_update["ai_fallback_message"] == "Бот временно отдыхает."

    # Проверка состояния в БД
    await db_session.refresh(test_user)
    assert decrypt_data(test_user.encrypted_ai_api_key) == "test_gemini_api_key_12345"
    assert test_user.ai_system_prompt == "You are a test bot."
    assert test_user.ai_fallback_message == "Бот временно отдыхает."

    # 2. Get settings
    response_get = await async_client.get("/api/v1/ai/settings", headers=auth_headers)
    assert response_get.status_code == 200
    data_get = response_get.json()
    assert data_get["provider"] == "google"
    assert data_get["model_name"] == "gemini-2.5-pro"
    assert data_get["ai_fallback_message"] == "Бот временно отдыхает."
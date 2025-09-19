# tests/api/test_ai.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.core.security import decrypt_data

pytestmark = pytest.mark.anyio

async def test_update_and_get_ai_settings(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User
):
    """Тест полного цикла CRUD для настроек ИИ."""
    # 1. Update settings
    update_data = {
        "provider": "google",
        "api_key": "test_gemini_api_key_12345",
        "model_name": "gemini-2.5-pro",
        "system_prompt": "You are a test bot."
    }
    response_update = await async_client.put("/api/v1/ai/settings", headers=auth_headers, json=update_data)
    
    assert response_update.status_code == 200
    data_update = response_update.json()
    assert data_update["provider"] == "google"
    assert data_update["is_configured"] is True

    # Check DB
    await db_session.refresh(test_user)
    assert decrypt_data(test_user.encrypted_ai_api_key) == "test_gemini_api_key_12345"
    assert test_user.ai_system_prompt == "You are a test bot."

    # 2. Get settings
    response_get = await async_client.get("/api/v1/ai/settings", headers=auth_headers)
    assert response_get.status_code == 200
    data_get = response_get.json()
    assert data_get["provider"] == "google"
    assert data_get["model_name"] == "gemini-2.5-pro"
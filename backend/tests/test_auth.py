import pytest
from httpx import AsyncClient
from app.core.config import settings

pytestmark = pytest.mark.asyncio

async def test_login(async_client: AsyncClient):
    """Тест реального логина. Создаст или обновит пользователя в вашей БД."""
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    assert test_token, "Переменная VK_HEALTH_CHECK_TOKEN должна быть в .env"

    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    
    assert response.status_code == 200
    assert "access_token" in response.json()

async def test_login_invalid_token(async_client: AsyncClient):
    """Тест входа с невалидным токеном."""
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": "invalid_token"})
    assert response.status_code == 401
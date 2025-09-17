# tests/api/test_auth.py
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from app.main import app
from app.api.dependencies import limiter

# Создаем пустую асинхронную функцию-заглушку
async def override_limiter():
    pass

# Переопределяем зависимость limiter на нашу заглушку
app.dependency_overrides[limiter] = override_limiter


# ИЗМЕНЕНИЕ: Замените pytestmark на этот маркер для каждой функции
@pytest.mark.anyio
async def test_login_via_vk_new_user(async_client: AsyncClient, mocker):
    """Тест успешного логина и создания нового пользователя."""
    mocker.patch('app.api.endpoints.auth.is_token_valid', return_value=987654)

    response = await async_client.post(
        "/api/v1/auth/vk",
        json={"vk_token": "valid_new_user_token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "manager_id" in data
    assert "active_profile_id" in data
    assert data["manager_id"] == data["active_profile_id"]


@pytest.mark.anyio
async def test_login_via_vk_existing_user(async_client: AsyncClient, mocker, test_user):
    """Тест успешного логина для уже существующего пользователя."""
    mocker.patch('app.api.endpoints.auth.is_token_valid', return_value=test_user.vk_id)

    response = await async_client.post(
        "/api/v1/auth/vk",
        json={"vk_token": "valid_existing_user_token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["manager_id"] == test_user.id
    assert data["active_profile_id"] == test_user.id


@pytest.mark.anyio
async def test_login_via_vk_invalid_token(async_client: AsyncClient, mocker):
    """Тест на ошибку при невалидном VK токене."""
    mocker.patch('app.api.endpoints.auth.is_token_valid', return_value=None)

    response = await async_client.post(
        "/api/v1/auth/vk",
        json={"vk_token": "invalid_token"}
    )

    assert response.status_code == 401
    assert "Неверный или просроченный токен VK" in response.text
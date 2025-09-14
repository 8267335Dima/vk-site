import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User

# Помечаем все тесты в этом файле как асинхронные
pytestmark = pytest.mark.asyncio


async def test_login_new_user(async_client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """
    Тест успешного входа нового пользователя.
    1. Мокаем внешний вызов к VK API.
    2. Отправляем запрос на эндпоинт /auth/vk.
    3. Проверяем успешный статус-код и тело ответа.
    4. Проверяем, что в базе данных действительно был создан новый пользователь.
    """
    # 1. Мокаем функцию is_token_valid, чтобы она не делала реальный запрос к VK
    async def mock_is_token_valid(token):
        return 123456789  # Возвращаем фейковый VK ID

    monkeypatch.setattr("app.api.endpoints.auth.is_token_valid", mock_is_token_valid)

    # 2. Отправляем запрос на логин
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": "valid_fake_token"})

    # 3. Проверяем ответ от API
    assert response.status_code == 200
    response_data = response.json()
    assert "access_token" in response_data
    assert response_data["token_type"] == "bearer"

    # 4. Проверяем состояние базы данных
    stmt = select(User).where(User.vk_id == 123456789)
    result = await db_session.execute(stmt)
    user_in_db = result.scalar_one_or_none()

    assert user_in_db is not None
    assert user_in_db.vk_id == 123456789
    assert user_in_db.plan == "Базовый"


async def test_login_invalid_token(async_client: AsyncClient, monkeypatch):
    """
    Тест попытки входа с невалидным токеном.
    """
    # Мокаем is_token_valid, чтобы она возвращала None, имитируя невалидный токен
    async def mock_is_token_valid_failed(token):
        return None

    monkeypatch.setattr("app.api.endpoints.auth.is_token_valid", mock_is_token_valid_failed)

    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": "invalid_fake_token"})

    assert response.status_code == 401
    assert "Неверный или просроченный токен VK" in response.json()["detail"]
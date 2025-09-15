# backend/tests/conftest.py

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from asgi_lifespan import LifespanManager
from sqlalchemy import select
from typing import AsyncGenerator
from app.db.session import get_db, AsyncSessionFactory
from app.main import app
from app.api.dependencies import limiter
from app.db.models import User
from app.services.vk_api import VKAPI
from app.core.config import settings
from app.core.security import decrypt_data
from app.core.constants import PlanName

# Меняем scope на "module", чтобы клиент и сессия создавались один раз на весь модуль тестов
# Это значительно ускоряет выполнение
@pytest_asyncio.fixture(scope="module")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

@pytest_asyncio.fixture(scope="module")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]: 
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[limiter] = lambda: None  # Отключаем rate limiter в тестах
    
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="module")
async def authorized_user_and_headers(async_client: AsyncClient, db_session: AsyncSession) -> tuple[User, dict]:
    """
    Выполняет вход ОДИН РАЗ для всего модуля тестов, переводит пользователя на PRO тариф
    и возвращает объект User и заголовки.
    """
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    assert test_token, "Переменная VK_HEALTH_CHECK_TOKEN должна быть в .env"

    r = await async_client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    assert r.status_code == 200, f"Не удалось авторизоваться: {r.text}"
    
    response_data = r.json()
    access_token = response_data.get("access_token")
    user_id = response_data.get("manager_id")
    
    headers = {"Authorization": f"Bearer {access_token}"}

    user = await db_session.get(User, user_id)
    assert user is not None, "Не удалось найти пользователя в БД после логина"

    # Принудительно ставим PRO тариф для доступа ко всем функциям
    if user.plan != PlanName.PRO:
        user.plan = PlanName.PRO
        await db_session.commit()
        await db_session.refresh(user)

    return user, headers

@pytest_asyncio.fixture(scope="module")
async def vk_api_client(authorized_user_and_headers: tuple[User, dict]) -> VKAPI:
    """Создает и предоставляет реальный клиент VK API для тестов."""
    user, _ = authorized_user_and_headers
    token = decrypt_data(user.encrypted_vk_token)
    assert token, "Не удалось расшифровать токен VK"
    
    api_client = VKAPI(access_token=token)
    # Сохраняем ID пользователя для удобства
    setattr(api_client, "user_id", user.vk_id)
    
    return api_client
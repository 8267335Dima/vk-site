# backend/tests/conftest.py

import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from asgi_lifespan import LifespanManager

from app.db.models import User
from app.db.session import get_db, AsyncSessionFactory
from app.main import app
from app.api.dependencies import limiter
from sqlalchemy.orm import selectinload
from app.services.vk_api import VKAPI
from app.core.config import settings
from app.core.security import decrypt_data

# --- ИЗМЕНЕНИЕ 1: МЕНЯЕМ SCOPE НА "module" ---
@pytest_asyncio.fixture(scope="module")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

# --- ИЗМЕНЕНИЕ 2: МЕНЯЕМ SCOPE НА "module" ---
@pytest_asyncio.fixture(scope="module")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    async def _override_limiter():
        pass
    
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[limiter] = _override_limiter
    
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    
    app.dependency_overrides.clear()

# --- ЭТА ФИКСТУРА ОСТАЕТСЯ С SCOPE="function", ТАК КАК ОНА МОЖЕТ ИЗМЕНЯТЬ ДАННЫЕ В БД ---
@pytest_asyncio.fixture(scope="function")
async def authorized_user_and_headers(async_client: AsyncClient, db_session: AsyncSession) -> tuple[User, dict]:
    """
    Выполняет вход и возвращает объект User и заголовки.
    Создается заново для каждого теста.
    """
    test_token = settings.VK_HEALTH_CHECK_TOKEN
    assert test_token, "Переменная VK_HEALTH_CHECK_TOKEN должна быть в .env"

    r = await async_client.post("/api/v1/auth/vk", json={"vk_token": test_token})
    assert r.status_code == 200
    
    response_data = r.json()
    access_token = response_data.get("access_token")
    user_id = response_data.get("manager_id")
    
    assert access_token and user_id, "В ответе на логин отсутствуют access_token или manager_id"
    
    headers = {"Authorization": f"Bearer {access_token}"}

    # Используем selectinload для "жадной" загрузки связанных прокси
    stmt = select(User).options(selectinload(User.proxies)).where(User.id == user_id)
    user = (await db_session.execute(stmt)).scalar_one_or_none()
    
    assert user is not None, "Не удалось найти пользователя в БД после логина"

    return user, headers

@pytest.fixture(scope="module")
async def vk_api_client_module(async_client: AsyncClient, db_session: AsyncSession) -> VKAPI:
    """
    Создает VK API клиент один раз для всего тестового модуля.
    """
    print("\n[MODULE_FIXTURE] Авторизация и создание VK API клиента...")
    
    response = await async_client.post("/api/v1/auth/vk", json={"vk_token": settings.VK_HEALTH_CHECK_TOKEN})
    assert response.status_code == 200
    user_id = response.json()['manager_id']
    
    user = await db_session.get(User, user_id)
    assert user is not None
    
    token = decrypt_data(user.encrypted_vk_token)
    assert token
    
    api_client = VKAPI(access_token=token)
    setattr(api_client, 'user_id', user.vk_id)
    
    return api_client
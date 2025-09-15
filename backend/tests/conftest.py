# --- backend/tests/conftest.py ---

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
from app.core.config import settings


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
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

@pytest_asyncio.fixture(scope="function")
async def authorized_user_and_headers(async_client: AsyncClient, db_session: AsyncSession) -> tuple[User, dict]:
    """
    Выполняет вход, СОХРАНЯЕТ пользователя в БД, и возвращает:
    1. Объект User, присоединенный к сессии теста, с предзагруженными proxies.
    2. Заголовки для авторизованных запросов.
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

    stmt = select(User).options(selectinload(User.proxies)).where(User.id == user_id)
    result = await db_session.execute(stmt)
    user = result.scalar_one_or_none()
    
    assert user is not None, "Не удалось найти пользователя в БД после логина"

    return user, headers
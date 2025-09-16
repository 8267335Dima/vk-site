# backend/tests/conftest.py

import asyncio
import sys
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.api.dependencies import limiter
from app.core.config import settings
from app.core.constants import PlanName
from app.core.security import decrypt_data
from app.db.base import Base
from app.db.models import User
from app.db.session import get_db
from app.services.vk_api import VKAPI


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Для КАЖДОГО теста:
    1. Создает новый движок, подключенный к тестовой БД.
    2. Создает все таблицы с нуля.
    3. Предоставляет сессию в транзакции.
    4. После теста откатывает транзакцию, удаляет все таблицы и закрывает соединение.
    Это обеспечивает 100% изоляцию тестов.
    """
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as connection:
        async with connection.begin() as transaction:
            session = AsyncSession(bind=connection, expire_on_commit=False)
            yield session
            await transaction.rollback()

    await engine.dispose()


@pytest.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Предоставляет тестовый HTTP-клиент для каждого теста.
    """
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[limiter] = lambda: None

    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def authorized_user_and_headers(async_client: AsyncClient, db_session: AsyncSession) -> tuple[User, dict]:
    """
    Авторизует пользователя для каждого теста.
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
    assert user is not None

    if user.plan != PlanName.PRO:
        user.plan = PlanName.PRO
        await db_session.commit()
        await db_session.refresh(user)

    return user, headers

@pytest.fixture(scope="function")
async def vk_api_client(authorized_user_and_headers: tuple[User, dict]) -> AsyncGenerator[VKAPI, None]:
    """
    Предоставляет клиент для VK API.
    """
    user, _ = authorized_user_and_headers
    token = decrypt_data(user.encrypted_vk_token)
    assert token, "Не удалось расшифровать токен VK"

    api_client = VKAPI(access_token=token)
    setattr(api_client, "user_id", user.vk_id)

    yield api_client
    await api_client.close()
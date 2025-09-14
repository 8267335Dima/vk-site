import asyncio
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.config import settings

# УЛУЧШЕНИЕ: Создаем отдельный движок для тестовой базы данных
# Используем данные из pytest.ini
test_db_url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
engine_test = create_async_engine(test_db_url, pool_pre_ping=True)
async_session_maker = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

# Переопределяем зависимость get_db, чтобы тесты использовали тестовую БД
async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

app.dependency_overrides[get_db] = override_get_async_session

@pytest.fixture(scope='session', autouse=True)
async def setup_database():
    """Фикстура для создания и удаления таблиц в тестовой БД один раз за сессию."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="session")
def event_loop():
    """Создает экземпляр event loop для всей тестовой сессии."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Фикстура для создания асинхронного HTTP-клиента для тестов API."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
# backend/tests/conftest.py
import asyncio
from typing import AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from asgi_lifespan import LifespanManager

# --- ИСПОЛЬЗУЕМ ЗАВИСИМОСТИ ИЗ ОСНОВНОГО ПРИЛОЖЕНИЯ ---
from app.db.session import get_db, AsyncSessionFactory
from app.main import app
from app.api.dependencies import limiter # Импортируем лимитер для отключения

# --- ФИНАЛЬНАЯ КОНФИГУРАЦИЯ ТЕСТОВ ---

# ИСПРАВЛЕНИЕ: Фикстура event_loop полностью удалена.
# pytest-asyncio теперь сам управляет циклом событий, что решает
# ошибки 'RuntimeError: Event loop is closed' и 'attached to a different loop'.
# Это современный и единственно верный подход.

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Предоставляет сессию к ВАШЕЙ РЕАЛЬНОЙ БАЗЕ ДАННЫХ.
    Все изменения, которые будут закоммичены в тестах, ОСТАНУТСЯ в базе.
    """
    async with AsyncSessionFactory() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Главный клиент для API-запросов.
    Запускает приложение, подменяет сессию БД и отключает rate-limiter.
    """
    # Подменяем зависимость get_db на нашу сессию
    async def _override_get_db():
        yield db_session

    # Отключаем rate-limiter, чтобы тесты не падали с ошибкой 429
    async def _override_limiter():
        pass
    
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[limiter] = _override_limiter
    
    # Запускаем приложение с его жизненным циклом (инициализация Redis и т.д.)
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    
    # Очищаем подмену после теста
    app.dependency_overrides.clear()
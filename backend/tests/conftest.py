# tests/conftest.py
import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

# --- Переопределяем переменные окружения для тестов ---
# Это гарантирует, что приложение при импорте будет использовать тестовую БД
import os
os.environ['ENV_FILE'] = os.path.join(os.path.dirname(__file__), '..', '.env')

from app.main import app
from app.db.session import get_db, engine as main_engine
from app.db.base import Base
from app.core.config import settings
from app.db.models import User
from app.core.security import create_access_token, encrypt_data
from app.core.constants import PlanName
from app.core.plans import get_limits_for_plan


# Создаем отдельный движок и сессии для тестовой БД
test_engine = create_async_engine(settings.database_url, echo=False)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine, class_=AsyncSession
)

# Переопределяем зависимость get_db для использования тестовой сессии
async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Создает экземпляр event loop для всего тестового сеанса."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Применяет миграции Alembic в начале сессии и откатывает их в конце.
    `autouse=True` означает, что эта фикстура будет запускаться автоматически.
    """
    alembic_cfg = Config("alembic.ini")
    
    # Применяем миграции
    command.upgrade(alembic_cfg, "head")

    yield

    # Откатываем миграции
    command.downgrade(alembic_cfg, "base")


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Предоставляет сессию БД для каждого теста, откатывая транзакцию после завершения.
    Это гарантирует, что тесты не влияют друг на друга.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    Создает тестовый клиент для отправки HTTP-запросов к приложению.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Создает и возвращает тестового пользователя в БД."""
    user_data = {
        "vk_id": 12345678,
        "encrypted_vk_token": encrypt_data("test_vk_token"),
        "plan": PlanName.PRO.name,
    }
    limits = get_limits_for_plan(PlanName.PRO)
    user = User(**user_data, **limits)
    
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
def auth_headers(test_user: User) -> dict[str, str]:
    """Генерирует заголовки авторизации для тестового пользователя."""
    token_data = {"sub": str(test_user.id), "profile_id": str(test_user.id)}
    access_token = create_access_token(data=token_data)
    return {"Authorization": f"Bearer {access_token}"}
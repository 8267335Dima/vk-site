# tests/conftest.py

import os
import uuid
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock
from redis.asyncio import Redis as AsyncRedis
# Указываем pytest использовать тестовую конфигурацию до импорта любых модулей приложения.
os.environ['ENV_FILE'] = os.path.join(os.path.dirname(__file__), '..', '.env.test')
from fastapi_limiter import FastAPILimiter
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient # <<< ИЗМЕНЕНИЕ: Импортируем TestClient из FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.db.models import User
from app.db.session import get_db
from app.core.config import settings
from app.core.constants import PlanName
from app.core.plans import get_limits_for_plan
from app.core.security import create_access_token, encrypt_data
from app.api.dependencies import get_db, get_arq_pool, get_current_active_profile
from app.services.event_emitter import RedisEventEmitter

# --- ОСНОВНЫЕ ФИКСТУРЫ ДАННЫХ И БД ---

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        TestingSessionLocal = sessionmaker(
            bind=connection, class_=AsyncSession, autocommit=False, autoflush=False, expire_on_commit=False
        )
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
            await connection.close()
            await engine.dispose()

@pytest.fixture(scope="function")
def mock_arq_pool(mocker) -> AsyncMock:
    mock_pool = AsyncMock()
    def create_mock_job(*args, **kwargs):
        mock_job = AsyncMock()
        mock_job.job_id = f"test_job_{uuid.uuid4()}"
        return mock_job
    mock_pool.enqueue_job = AsyncMock(side_effect=create_mock_job)
    mock_pool.abort_job = AsyncMock()
    return mock_pool

@pytest_asyncio.fixture(scope="function")
async def test_app(db_session: AsyncSession, mock_arq_pool: AsyncMock):
    async def override_get_db():
        yield db_session
    async def override_get_arq_pool():
        return mock_arq_pool

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool

    # 2. Вручную инициализируем лимитер перед запуском теста
    limiter_redis = AsyncRedis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        decode_responses=True
    )
    await FastAPILimiter.init(limiter_redis)
    
    yield app
    
    # 3. Вручную "закрываем" лимитер после теста
    FastAPILimiter.close()
    await limiter_redis.aclose() # Закрываем соединение с Redis
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    user_data = {
        "vk_id": 12345678, "encrypted_vk_token": encrypt_data("test_vk_token"), "plan": PlanName.PRO.name,
    }
    all_limits = get_limits_for_plan(PlanName.PRO)
    user_columns = {c.name for c in User.__table__.columns}
    valid_limits = {k: v for k, v in all_limits.items() if k in user_columns}
    user = User(**user_data, **valid_limits)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """
    Создает асинхронный httpx.AsyncClient для тестирования ASGI приложения.
    """

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
    # ----------------------
        yield client

@pytest.fixture(scope="function")
def auth_headers(test_user: User):
    async def override_get_current_active_profile():
        return test_user
    app.dependency_overrides[get_current_active_profile] = override_get_current_active_profile

    token_data = {"sub": str(test_user.id), "profile_id": str(test_user.id)}
    access_token = create_access_token(data=token_data)
    
    yield {"Authorization": f"Bearer {access_token}"}
    
    if get_current_active_profile in app.dependency_overrides:
        del app.dependency_overrides[get_current_active_profile]

# --- Остальные фикстуры без изменений ---
@pytest.fixture
def mock_emitter(mocker) -> RedisEventEmitter:
    mock_redis = AsyncMock()
    emitter = RedisEventEmitter(mock_redis)
    emitter.send_log = mocker.AsyncMock()
    emitter.send_stats_update = mocker.AsyncMock()
    emitter.send_task_status_update = mocker.AsyncMock()
    emitter.send_system_notification = mocker.AsyncMock()
    return emitter

@pytest_asyncio.fixture(scope="function")
async def manager_user(db_session: AsyncSession) -> User:
    user_data = {"vk_id": 111111, "encrypted_vk_token": encrypt_data("manager_token"), "plan": PlanName.AGENCY.name}
    limits = get_limits_for_plan(PlanName.AGENCY)
    user = User(**user_data, **{k: v for k, v in limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def managed_profile_user(db_session: AsyncSession) -> User:
    user_data = {"vk_id": 222222, "encrypted_vk_token": encrypt_data("managed_profile_token"), "plan": PlanName.PRO.name}
    limits = get_limits_for_plan(PlanName.PRO)
    user = User(**user_data, **{k: v for k, v in limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def team_member_user(db_session: AsyncSession) -> User:
    user_data = {"vk_id": 333333, "encrypted_vk_token": encrypt_data("team_member_token"), "plan": PlanName.BASE.name}
    limits = get_limits_for_plan(PlanName.BASE)
    user = User(**user_data, **{k: v for k, v in limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def get_auth_headers_for():
    def _get_auth_headers(user: User) -> dict[str, str]:
        token_data = {"sub": str(user.id), "profile_id": str(user.id)}
        access_token = create_access_token(data=token_data)
        return {"Authorization": f"Bearer {access_token}"}
    return _get_auth_headers
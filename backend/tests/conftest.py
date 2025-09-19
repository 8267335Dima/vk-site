# tests/conftest.py

import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock

from sqlalchemy import StaticPool

from app.services.event_emitter import RedisEventEmitter

# Устанавливаем переменную окружения ДО импорта приложения
os.environ['ENV_FILE'] = os.path.join(os.path.dirname(__file__), '..', '.env.test')

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.main import create_app
from app.db.base import Base
from app.db.models import User
from app.core.config import settings

# --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
# Импортируем Enum из правильного места
from app.core.enums import PlanName
from app.core.plans import get_limits_for_plan
from app.core.security import create_access_token, encrypt_data
from app.api.dependencies import get_db, get_arq_pool

# --- НАСТРОЙКА ТЕСТОВОГО ОКРУЖЕНИЯ ---

@pytest_asyncio.fixture(scope="function")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    is_sqlite = "sqlite" in settings.database_url
    
    engine = create_async_engine(
        settings.database_url,
        poolclass=StaticPool if is_sqlite else None,
        connect_args={"check_same_thread": False} if is_sqlite else {}
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def mock_arq_pool(mocker) -> AsyncMock:
    mock_pool = AsyncMock()
    def create_mock_job(*args, **kwargs):
        mock_job = AsyncMock()
        mock_job.job_id = f"test_job_{uuid.uuid4()}"
        return mock_job
    mock_pool.enqueue_job = AsyncMock(side_effect=create_mock_job)
    mock_pool.abort_job = AsyncMock()
    return mock_pool

@pytest.fixture(scope="function")
def test_app(db_engine: AsyncEngine, db_session: AsyncSession, mock_arq_pool: AsyncMock) -> FastAPI:
    app = create_app(db_engine=db_engine)

    class SQLAdminTestSessionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.session = db_session
            response = await call_next(request)
            return response

    app.add_middleware(SQLAdminTestSessionMiddleware)


    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_arq_pool] = lambda: mock_arq_pool
    
    return app


@pytest_asyncio.fixture(scope="function")
async def async_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as client:
        yield client

# --- ФИКСТУРЫ ДАННЫХ ---

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    user_data = { "vk_id": 12345678, "encrypted_vk_token": encrypt_data("test_vk_token"), "plan": PlanName.PRO.name }
    limits = get_limits_for_plan(PlanName.PRO)
    user = User(**user_data, **{k: v for k, v in limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> User:
    user_data = { "vk_id": int(settings.ADMIN_VK_ID), "encrypted_vk_token": encrypt_data("admin_vk_token"), "plan": PlanName.PRO.name, "is_admin": True }
    limits = get_limits_for_plan(PlanName.PRO)
    user = User(**user_data, **{k: v for k, v in limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

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
def auth_headers(test_user: User):
    token_data = {"sub": str(test_user.id), "profile_id": str(test_user.id)}
    access_token = create_access_token(data=token_data)
    return {"Authorization": f"Bearer {access_token}"}

@pytest_asyncio.fixture
async def mock_emitter(mocker) -> RedisEventEmitter:
    mock_redis = AsyncMock()
    emitter = RedisEventEmitter(mock_redis)
    emitter.send_log = mocker.AsyncMock()
    emitter.send_stats_update = mocker.AsyncMock()
    emitter.send_task_status_update = mocker.AsyncMock()
    emitter.send_system_notification = mocker.AsyncMock()
    return emitter

@pytest.fixture(scope="function")
def get_auth_headers_for():
    def _get_auth_headers(user: User) -> dict[str, str]:
        token_data = {"sub": str(user.id), "profile_id": str(user.id)}
        access_token = create_access_token(data=token_data)
        return {"Authorization": f"Bearer {access_token}"}
    return _get_auth_headers
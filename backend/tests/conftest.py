import os
import uuid
import json
from typing import AsyncGenerator
from unittest.mock import AsyncMock

from sqlalchemy import StaticPool, select

from app.services.event_emitter import RedisEventEmitter
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
from app.db.models import User, Plan
from app.core.config import settings
from app.core.enums import PlanName
from app.core.security import create_access_token, encrypt_data
from app.api.dependencies import get_db, get_arq_pool
from app.core.config_loader import PLAN_CONFIG

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
        plans_to_create = []
        for plan_id, config in PLAN_CONFIG.items():
            plan_data = config.model_dump()
            plan_data['name_id'] = plan_id
            plans_to_create.append(Plan(**plan_data))
        
        session.add_all(plans_to_create)
        await session.commit()
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

@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    user_data = { "vk_id": 12345678, "encrypted_vk_token": encrypt_data("test_vk_token"), "plan_id": pro_plan.id }
    user = User(**user_data, **{k: v for k, v in pro_plan.limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> User:
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    user_data = { "vk_id": int(settings.ADMIN_VK_ID), "encrypted_vk_token": encrypt_data("admin_vk_token"), "plan_id": pro_plan.id, "is_admin": True }
    user = User(**user_data, **{k: v for k, v in pro_plan.limits.items() if hasattr(User, k)})
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
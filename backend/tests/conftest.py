import asyncio
import sys
import os
import uuid
import json
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock

from sqlalchemy import StaticPool, select

from app.services.event_emitter import RedisEventEmitter
os.environ['ENV_FILE'] = os.path.join(os.path.dirname(__file__), '..', '.env.test')
from fastapi.testclient import TestClient
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
    
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    
    engine = create_async_engine(
        settings.database_url,
        poolclass=StaticPool if is_sqlite else None,
        connect_args=connect_args,
        json_serializer=json.dumps,
        json_deserializer=json.loads
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


# ▼▼▼ ОБНОВЛЕННАЯ И УЛУЧШЕННАЯ ФИКСТУРА ▼▼▼
@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Создает сессию БД для теста, которая работает внутри одной транзакции
    и откатывается после завершения теста. Это обеспечивает изоляцию
    и корректное закрытие соединений, устраняя RuntimeWarning.
    """
    # Устанавливаем соединение с БД на время всего теста
    connection = await db_engine.connect()
    # Начинаем транзакцию
    trans = await connection.begin()

    # Создаем сессию, привязанную к этому конкретному соединению
    session = AsyncSession(bind=connection, expire_on_commit=False)

    try:
        # Предварительно заполняем БД базовыми данными (например, тарифами),
        # которые будут доступны тесту, но откатятся после его завершения.
        plans_to_create = []
        plan_model_columns = {c.name for c in Plan.__table__.columns}
        for plan_id, config in PLAN_CONFIG.items():
            plan_data = config.model_dump()
            filtered_data = {
                key: value for key, value in plan_data.items()
                if key in plan_model_columns
            }
            filtered_data['name_id'] = plan_id
            plans_to_create.append(Plan(**filtered_data))
        
        session.add_all(plans_to_create)
        await session.commit() # Этот commit работает внутри транзакции

        yield session

    finally:
        # Блок finally гарантирует, что ресурсы будут освобождены,
        # даже если тест упадет с ошибкой.
        await session.close()
        # Откатываем транзакцию, чтобы очистить БД для следующего теста
        await trans.rollback()
        # Закрываем соединение
        await connection.close()


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

@pytest_asyncio.fixture(scope="function")
async def mock_redis() -> AsyncMock:
    """
    Эта фикстура создает и предоставляет мок-объект для клиента Redis.
    Она нужна, чтобы заменить реальное подключение к Redis в тестах.
    """
    mock = AsyncMock()
    # Настраиваем поведение мока по умолчанию
    mock.get.return_value = None
    mock.set.return_value = True
    return mock

# ▼▼▼ ШАГ 2: ЗАМЕНИТЕ ВАШУ ФИКСТУРУ test_app НА ЭТУ ▼▼▼
@pytest.fixture(scope="function")
def test_app(
    db_engine: AsyncEngine,
    db_session: AsyncSession,
    mock_arq_pool: AsyncMock,
    mock_redis: AsyncMock, # <--- Теперь pytest сможет найти эту фикстуру
    mocker
) -> FastAPI:
    # Патчим (заменяем) функции, которые создают реальные подключения в lifespan,
    # чтобы они не выполнялись во время тестов. Это не обязательно, но делает тесты
    # более надежными и независимыми от кода в lifespan.
    mocker.patch("app.main.create_pool", return_value=mock_arq_pool)
    mocker.patch("app.main.AsyncRedis.from_url", return_value=mock_redis)
    mocker.patch("app.main.FastAPILimiter.init", return_value=None)
    mocker.patch("app.main.run_redis_listener", return_value=None)

    app = create_app(db_engine=db_engine)

    # Явно устанавливаем моки в состояние приложения. Это ключевой момент,
    # который исправляет ошибку `AttributeError`. Теперь middleware
    # найдет `app.state.activity_redis`.
    app.state.arq_pool = mock_arq_pool
    app.state.activity_redis = mock_redis
    app.state.redis_client = mock_redis

    class SQLAdminTestSessionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.session = db_session
            response = await call_next(request)
            return response

    app.add_middleware(SQLAdminTestSessionMiddleware)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_arq_pool] = lambda: mock_arq_pool
    
    return app

# ▼▼▼ ШАГ 3: УБЕДИТЕСЬ, ЧТО ФИКСТУРА async_client ИСПОЛЬЗУЕТ КОНТЕКСТНЫЙ МЕНЕДЖЕР ▼▼▼
# Это гарантирует, что lifespan приложения (который мы теперь мокаем) будет
# корректно запущен и завершен для каждого теста.
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

@pytest.fixture(scope="function")
def get_auth_headers_for():
    """Фикстура-фабрика для создания auth-заголовков для конкретного пользователя."""
    def _get_headers(user: User) -> dict[str, str]:
        token_data = {"sub": str(user.id), "profile_id": str(user.id)}
        access_token = create_access_token(data=token_data)
        return {"Authorization": f"Bearer {access_token}"}
    return _get_headers

@pytest_asyncio.fixture(scope="function")
async def manager_user(db_session: AsyncSession) -> User:
    """Создает пользователя с тарифом 'Agency', который может быть менеджером команды."""
    agency_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.AGENCY.name))).scalar_one()
    user_data = { "vk_id": 1111, "encrypted_vk_token": encrypt_data("manager_token"), "plan_id": agency_plan.id }
    user = User(**user_data, **{k: v for k, v in agency_plan.limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def team_member_user(db_session: AsyncSession) -> User:
    """Создает обычного пользователя, который будет членом команды."""
    base_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.BASE.name))).scalar_one()
    user_data = { "vk_id": 2222, "encrypted_vk_token": encrypt_data("member_token"), "plan_id": base_plan.id }
    user = User(**user_data, **{k: v for k, v in base_plan.limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def managed_profile_user(db_session: AsyncSession) -> User:
    """Создает пользователя, профилем которого будут управлять."""
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    user_data = { "vk_id": 3333, "encrypted_vk_token": encrypt_data("managed_token"), "plan_id": pro_plan.id }
    user = User(**user_data, **{k: v for k, v in pro_plan.limits.items() if hasattr(User, k)})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    """
    Создает синхронный тестовый клиент для API.
    Необходим для тестирования WebSocket.
    """
    with TestClient(test_app) as c:
        yield c
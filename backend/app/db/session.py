# backend/app/db/session.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

# --- Основной движок для записи и чтения ---
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0}
)

AsyncSessionFactory = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

# --- Движок только для чтения (если настроен) ---
read_engine: AsyncEngine | None = None
if settings.database_url_read:
    read_engine = create_async_engine(
        settings.database_url_read,
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0}
    )
    ReadAsyncSessionFactory = sessionmaker(
        autocommit=False, autoflush=False, bind=read_engine, class_=AsyncSession
    )
    log.info("database.read_replica.configured")
else:
    # Если реплика не настроена, сессии для чтения будут использовать основной движок
    ReadAsyncSessionFactory = AsyncSessionFactory
    log.info("database.read_replica.not_configured_using_main")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость для получения сессии для ЗАПИСИ/ЧТЕНИЯ (основная БД)."""
    async with AsyncSessionFactory() as session:
        yield session

async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость для получения сессии ТОЛЬКО ДЛЯ ЧТЕНИЯ (реплика или основная БД)."""
    async with ReadAsyncSessionFactory() as session:
        yield session
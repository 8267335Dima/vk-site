# backend/app/db/session.py

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Создаем асинхронный "движок" для SQLAlchemy
engine = create_async_engine(settings.database_url, pool_pre_ping=True, echo=True)

# Создаем фабрику асинхронных сессий
AsyncSessionFactory = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Зависимость (dependency) для FastAPI, которая предоставляет сессию базы данных.
    Гарантирует, что сессия будет закрыта после завершения запроса.
    """
    async with AsyncSessionFactory() as session:
        yield session
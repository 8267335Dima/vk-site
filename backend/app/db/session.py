# backend/app/db/session.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

AsyncSessionFactory = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session
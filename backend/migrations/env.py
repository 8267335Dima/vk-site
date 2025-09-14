import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# ----------------- КОНФИГУРАЦИЯ -----------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- ИЗМЕНЕНИЕ: УДАЛЯЕМ ИМПОРТ scheduler_models ---
from app.db.base import Base
# Убедитесь, что app/db/models/__init__.py импортирует все ВАШИ модели
from app.db.models import * 
from app.core.config import settings

target_metadata = Base.metadata

# ----------------- РЕЖИМЫ РАБОТЫ МИГРАЦИЙ -----------------

def run_migrations_offline() -> None:
    """Запускает миграции в 'offline' режиме."""
    url = settings.database_url.replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Общая функция для запуска миграций с использованием соединения."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Запускает миграции в 'online' режиме."""
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

# ----------------- ГЛАВНЫЙ БЛОК ВЫПОЛНЕНИЯ -----------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
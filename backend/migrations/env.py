import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# --- Импорт моделей и настроек проекта ---
from app.db.base import Base
from app.db.models import *  # Убедитесь, что app/db/models/__init__.py импортирует все ваши модели
from app.core.config import settings

# ----------------- КОНФИГУРАЦИЯ -----------------

# Конфигурационный объект Alembic
config = context.config

# Настройка логирования из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Целевая схема данных, с которой Alembic будет сравнивать реальную БД
target_metadata = Base.metadata

# ----------------- РЕЖИМЫ РАБОТЫ МИГРАЦИЙ -----------------

def run_migrations_offline() -> None:
    """Запускает миграции в 'offline' режиме (генерирует SQL-скрипт)."""
    # Используем синхронную версию URL для оффлайн-режима
    url = settings.database_url.replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # ИСПРАВЛЕНО: Добавляем эту строку, чтобы Alembic замечал изменения типов
        # колонок, например, с DateTime на DateTime(timezone=True).
        compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    """Общая функция для запуска миграций с использованием соединения."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # ИСПРАВЛЕНО: Эта настройка нужна и для онлайн-режима.
        compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Запускает миграции в 'online' режиме (применяет изменения к БД)."""
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
    # Проверяем, запущен ли уже цикл событий
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 'RuntimeError: There is no current event loop...'
        loop = None

    if loop and loop.is_running():
        # Если мы уже внутри цикла (как в pytest-asyncio), используем его
        loop.run_until_complete(run_migrations_online())
    else:
        # В противном случае (при запуске из консоли) создаем новый
        asyncio.run(run_migrations_online())
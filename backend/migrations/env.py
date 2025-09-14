from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
# Импортируем Base и ВСЕ МОДЕЛИ напрямую и явно.
# Это гарантирует, что Alembic видит их все, и решает проблемы с циклическими импортами.
from app.db.base import Base
from app.db.models.user import *
from app.db.models.task import *
from app.db.models.payment import *
from app.db.models.analytics import *
from app.db.models.shared import *
from app.db.scheduler_models import *
from app.core.config import settings

target_metadata = Base.metadata
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = settings.database_url.replace("+asyncpg", "") # Alembic работает в синхронном режиме
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=settings.database_url.replace("+asyncpg", "") # Alembic работает в синхронном режиме
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    # ИСПРАВЛЕНИЕ: Alembic v1.8+ требует асинхронного запуска для асинхронных драйверов
    import asyncio
    asyncio.run(run_migrations_online())
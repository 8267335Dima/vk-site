# backend/app/arq_config.py
from arq.connections import RedisSettings

# Единый источник настроек Redis для ARQ.
# Используем базу данных Redis №4, чтобы не пересекаться с кэшем или limiter'ом.
redis_settings = RedisSettings.from_dsn("redis://localhost:6379/4")
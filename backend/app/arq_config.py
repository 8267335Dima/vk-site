# backend/app/arq_config.py
from arq.connections import RedisSettings
from app.core.config import settings 
# Единый источник настроек Redis для ARQ.
# Используем базу данных Redis №4, чтобы не пересекаться с кэшем или limiter'ом.
redis_settings = RedisSettings(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    database=4
)
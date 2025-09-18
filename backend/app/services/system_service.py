# backend/app/services/system_service.py
from functools import lru_cache
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.system import GlobalSetting
from app.db.session import AsyncSessionFactory

class SystemService:
    _settings_cache = {}

    @classmethod
    async def _load_settings(cls):
        """Загружает все настройки из БД в кэш."""
        async with AsyncSessionFactory() as session:
            result = await session.execute(select(GlobalSetting))
            settings = result.scalars().all()
            cls._settings_cache = {s.key: {"value": s.value, "is_enabled": s.is_enabled} for s in settings}

    @classmethod
    @lru_cache(maxsize=128)
    def _get_setting_sync(cls, key: str, default: any):
        """Синхронный метод для получения значения из кэша. Используется lru_cache."""
        return cls._settings_cache.get(key, default)

    @classmethod
    async def get_setting(cls, key: str, default: any = None):
        """Асинхронный метод для получения настройки. При необходимости обновляет кэш."""
        if not cls._settings_cache:
            await cls._load_settings()
        return cls._get_setting_sync(key, default)

    @classmethod
    async def is_feature_enabled(cls, feature_key: str) -> bool:
        """Проверяет, включена ли глобально определенная функция."""
        setting = await cls.get_setting(f"feature:{feature_key}")
        if setting:
            return setting.get("is_enabled", True)
        # Если настройки нет, по умолчанию считаем фичу включенной
        return True

    @classmethod
    async def get_ticket_reopen_limit(cls) -> int:
        """Получает лимит на переоткрытие тикетов."""
        setting = await cls.get_setting("tickets:reopen_limit")
        if setting and isinstance(setting.get("value"), int):
            return setting["value"]
        return 3 # Значение по умолчанию

    @classmethod
    async def get_daily_ticket_creation_limit(cls) -> int:
        """Получает дневной лимит на создание тикетов."""
        setting = await cls.get_setting("tickets:daily_creation_limit")
        if setting and isinstance(setting.get("value"), int):
            return setting["value"]
        return 5 # Значение по умолчанию
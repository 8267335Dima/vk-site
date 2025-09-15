# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

# --- ИЗМЕНЕНИЕ: Определяем абсолютный путь к .env файлу ---
# Это гарантирует, что .env будет найден, независимо от точки запуска приложения.
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    REDIS_HOST: str
    REDIS_PORT: int

    VK_HEALTH_CHECK_TOKEN: Optional[str] = None
    VK_TEST_USER_ID: Optional[str] = None
    VK_TEST_FRIEND_ID: Optional[str] = None

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    SECRET_KEY: str
    ENCRYPTION_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    VK_API_VERSION: str
    ADMIN_VK_ID: str
    
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str

    ADMIN_USER: str
    ADMIN_PASSWORD: str
    ADMIN_IP_WHITELIST: Optional[str] = None

    ALLOWED_ORIGINS: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field
from typing import Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    POSTGRES_SERVER_READ: Optional[str] = None
    POSTGRES_PORT_READ: Optional[int] = None
    POSTGRES_USER_READ: Optional[str] = None
    POSTGRES_PASSWORD_READ: Optional[str] = None
    POSTGRES_DB_READ: Optional[str] = None

    @computed_field
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @computed_field
    @property
    def database_url_read(self) -> Optional[str]:
        if not all([self.POSTGRES_SERVER_READ, self.POSTGRES_USER_READ, self.POSTGRES_PASSWORD_READ, self.POSTGRES_DB_READ]):
            return None
        port = self.POSTGRES_PORT_READ or 5432
        return f"postgresql+asyncpg://{self.POSTGRES_USER_READ}:{self.POSTGRES_PASSWORD_READ}@{self.POSTGRES_SERVER_READ}:{port}/{self.POSTGRES_DB_READ}"

    REDIS_HOST: str
    REDIS_PORT: int
    VK_HEALTH_CHECK_TOKEN: Optional[str] = None
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 525600
    VK_API_VERSION: str
    ADMIN_VK_ID: str
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    ADMIN_USER: str
    ADMIN_PASSWORD: str
    ADMIN_IP_WHITELIST: Optional[str] = None
    ALLOWED_ORIGINS: str
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()
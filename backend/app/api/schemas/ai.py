# backend/app/api/schemas/ai.py
from pydantic import BaseModel, Field
from typing import Literal, Optional

AIProvider = Literal["openai", "google"]

class AISettingsUpdate(BaseModel):
    provider: AIProvider = Field(..., description="Провайдер ИИ")
    api_key: str = Field(..., min_length=10, description="API ключ от сервиса")
    model_name: str = Field("gemini-1.5-flash", description="Название модели")
    system_prompt: str = Field("", max_length=2000, description="Системная инструкция для модели")
    ai_fallback_message: Optional[str] = Field(None, max_length=1000, description="Сообщение-заглушка при ошибке AI")

class AISettingsRead(BaseModel):
    provider: Optional[AIProvider] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    is_configured: bool
    ai_fallback_message: Optional[str] = None
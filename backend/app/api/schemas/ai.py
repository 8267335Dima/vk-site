# backend/app/api/schemas/ai.py
from pydantic import BaseModel, Field
from typing import Literal

AIProvider = Literal["openai", "google"]

class AISettingsUpdate(BaseModel):
    provider: AIProvider = Field(..., description="Провайдер ИИ")
    api_key: str = Field(..., min_length=10, description="API ключ от сервиса")
    model_name: str = Field("gemini-2.5-flash", description="Название модели")
    system_prompt: str = Field("Ты — полезный ассистент.", max_length=2000)

class AISettingsUpdate(BaseModel):
    provider: AIProvider = Field(..., description="Провайдер ИИ")
    api_key: str = Field(..., min_length=10, description="API ключ от сервиса")
    model_name: str = Field("gemini-1.5-flash", description="Название модели")
    system_prompt: str = Field("", max_length=2000, description="Системная инструкция для модели")
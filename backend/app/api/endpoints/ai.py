# backend/app/api/endpoints/ai.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import User
from app.api.dependencies import get_current_active_profile
from app.api.schemas.ai import AISettingsUpdate, AISettingsRead
from app.core.security import encrypt_data, decrypt_data

router = APIRouter()

@router.put("/settings", response_model=AISettingsRead)
async def update_ai_settings(
    settings_data: AISettingsUpdate,
    user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Обновляет и шифрует настройки ИИ для пользователя."""
    user.ai_provider = settings_data.provider
    user.encrypted_ai_api_key = encrypt_data(settings_data.api_key)
    user.ai_model_name = settings_data.model_name
    user.ai_system_prompt = settings_data.system_prompt
    
    await db.commit()
    
    return AISettingsRead(
        provider=user.ai_provider,
        model_name=user.ai_model_name,
        system_prompt=user.ai_system_prompt,
        is_configured=bool(user.encrypted_ai_api_key)
    )

@router.get("/settings", response_model=AISettingsRead)
async def get_ai_settings(user: User = Depends(get_current_active_profile)):
    """Возвращает текущие настройки ИИ пользователя (без ключа)."""
    return AISettingsRead(
        provider=user.ai_provider,
        model_name=user.ai_model_name,
        system_prompt=user.ai_system_prompt,
        is_configured=bool(user.encrypted_ai_api_key)
    )
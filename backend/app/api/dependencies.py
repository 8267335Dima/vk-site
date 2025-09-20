# backend/app/api/dependencies.py
from typing import Annotated, Dict, Any
from arq import ArqRedis
from fastapi import Depends, HTTPException, Request, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import select, and_ 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import User, ManagedProfile, TeamMember, TeamProfileAccess
from app.db.session import get_db, AsyncSessionFactory
from app.repositories.user import UserRepository
from fastapi_limiter.depends import RateLimiter

from app.ai.unified_service import UnifiedAIService
from app.core.security import decrypt_data
from app.core.exceptions import UserActionException


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/vk")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_request_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.client.host if request.client else "unknown"

limiter = RateLimiter(times=5, minutes=1, identifier=get_request_identifier)

async def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool

async def get_token_payload(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except (JWTError, ValidationError):
        raise credentials_exception

async def _get_payload_from_string(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except (JWTError, ValidationError):
        raise credentials_exception
    
async def get_current_manager_user(
    payload: Dict[str, Any] = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db)
) -> User:
    user_repo = UserRepository(db)
    manager_id_str: str | None = payload.get("sub")
    if manager_id_str is None:
        raise credentials_exception
    
    manager = await user_repo.get(User, int(manager_id_str))
    if manager is None:
        raise credentials_exception
    return manager

# --- ИСПРАВЛЕННАЯ ЛОГИКА ---
async def get_current_active_profile(
    payload: Dict[str, Any] = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Определяет активный профиль на основе JWT токена.
    Эта функция ДОВЕРЯЕТ содержимому токена, так как эндпоинт /switch-profile
    уже проверил права доступа перед его выдачей.
    """
    manager_id_str = payload.get("sub")
    active_profile_id_str = payload.get("profile_id")

    if not manager_id_str:
        raise credentials_exception

    # Если 'profile_id' в токене нет, значит, пользователь работает со своим профилем.
    target_user_id = int(active_profile_id_str or manager_id_str)

    # Просто загружаем нужный профиль из БД.
    # Повторная проверка связи ManagedProfile здесь не нужна.
    active_profile = await db.get(User, target_user_id)
    
    if not active_profile:
        raise HTTPException(status_code=404, detail="Активный профиль не найден.")
        
    return active_profile
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


async def get_current_user_from_ws(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db) 
) -> User:
    payload = await _get_payload_from_string(token)
    profile_id = int(payload.get("profile_id") or payload.get("sub"))
    user = await db.get(User, profile_id)  
    if not user:
        raise credentials_exception
    return user

async def get_ai_service(user: User = Depends(get_current_active_profile)) -> UnifiedAIService:
    """
    Зависимость для создания экземпляра AI-сервиса с настройками
    текущего пользователя из базы данных.
    """
    api_key = decrypt_data(user.encrypted_ai_api_key)
    
    if not all([user.ai_provider, api_key, user.ai_model_name]):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="Настройки AI не сконфигурированы. Пожалуйста, укажите провайдера, модель и API ключ в настройках."
        )
    
    # ИЗМЕНЕНИЕ: Получаем заглушку или используем стандартную
    fallback = user.ai_fallback_message or "Извините, в данный момент не могу ответить."
    
    try:
        return UnifiedAIService(
            provider=user.ai_provider,
            api_key=api_key,
            model=user.ai_model_name,
            # И передаем ее в сервис
            fallback_message=fallback
        )
    except UserActionException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
# backend/app/api/endpoints/auth.py
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi_limiter.depends import RateLimiter

from app.db.session import get_db
from app.db.models import User, LoginHistory
from app.api.schemas.auth import TokenResponse
from app.services.vk_api import is_token_valid
from app.core.security import create_access_token, encrypt_data
from app.core.config import settings
from app.core.plans import get_limits_for_plan

router = APIRouter()

class TokenRequest(BaseModel):
    vk_token: str

@router.post(
    "/vk", 
    response_model=TokenResponse, 
    summary="Аутентификация или регистрация по токену VK",
    dependencies=[Depends(RateLimiter(times=5, minutes=1))]
)
async def login_via_vk(
    *,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token_request: TokenRequest
) -> TokenResponse:
    """
    Принимает 'vk_token', проверяет его, находит или создает пользователя.
    - Для новых пользователей: назначает пробный период ('Базовый' тариф на 14 дней).
    - Для существующих: обновляет их VK токен.
    - Для всех: записывает историю входа и возвращает JWT-токен для доступа к API.
    """
    vk_token = token_request.vk_token
    
    # 1. Валидация токена VK
    vk_id = await is_token_valid(vk_token)
    if not vk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или просроченный токен VK.",
        )

    # 2. Поиск или создание пользователя
    query = select(User).where(User.vk_id == vk_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    encrypted_token = encrypt_data(vk_token)
    
    base_plan_limits = get_limits_for_plan("Базовый")

    if user:
        # Если пользователь существует, просто обновляем его токен
        user.encrypted_vk_token = encrypted_token
    else:
        # Если пользователь новый, создаем его с пробным "Базовым" тарифом
        user = User(
            vk_id=vk_id, 
            encrypted_vk_token=encrypted_token,
            plan="Базовый",
            plan_expires_at=datetime.utcnow() + timedelta(days=14),
            daily_likes_limit=base_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=base_plan_limits["daily_add_friends_limit"]
        )
        db.add(user)

    # 3. Специальная логика для администратора
    if str(vk_id) == settings.ADMIN_VK_ID:
        admin_limits = get_limits_for_plan("PRO")
        user.is_admin = True
        user.plan = "PRO"
        user.plan_expires_at = None # Бессрочный тариф
        user.daily_likes_limit = admin_limits["daily_likes_limit"]
        user.daily_add_friends_limit = admin_limits["daily_add_friends_limit"]

    # Отправляем изменения в БД, чтобы получить user.id для нового пользователя
    await db.flush()
    await db.refresh(user)

    # 4. Логика записи в LoginHistory
    login_entry = LoginHistory(
        user_id=user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", "unknown")
    )
    db.add(login_entry)

    ### --- ГЛАВНОЕ ИСПРАВЛЕНИЕ --- ###
    # Сохраняем ID пользователя в переменную ПЕРЕД коммитом,
    # так как после коммита объект 'user' станет "просроченным".
    user_id_for_token = user.id
    
    # Единственный коммит в конце всех операций
    await db.commit()

    # 5. Логика создания JWT-токена
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Используем сохраненный ID для создания токена
    access_token = create_access_token(
        data={"sub": str(user_id_for_token)}, expires_delta=access_token_expires
    )

    return TokenResponse(access_token=access_token, token_type="bearer")
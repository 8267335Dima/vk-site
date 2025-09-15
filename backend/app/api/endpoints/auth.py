# backend/app/api/endpoints/auth.py

from datetime import timedelta, datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import User, LoginHistory
from app.api.schemas.auth import EnrichedTokenResponse
from app.services.vk_api import is_token_valid
from app.core.security import create_access_token, encrypt_data
from app.core.config import settings
from app.core.plans import get_limits_for_plan
from app.core.constants import PlanName
from app.api.dependencies import get_current_manager_user, limiter # Импортируем limiter

router = APIRouter()

class TokenRequest(BaseModel):
    vk_token: str


@router.post(
    "/vk",
    response_model=EnrichedTokenResponse,
    summary="Аутентификация или регистрация по токену VK",
    dependencies=[Depends(limiter)] # Оставляем защиту для production
)
async def login_via_vk(
    *,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token_request: TokenRequest
) -> EnrichedTokenResponse:
    vk_token = token_request.vk_token

    vk_id = await is_token_valid(vk_token)
    if not vk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или просроченный токен VK.",
        )

    query = select(User).where(User.vk_id == vk_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    encrypted_token = encrypt_data(vk_token)
    
    base_plan_limits = get_limits_for_plan(PlanName.BASE)

    if user:
        user.encrypted_vk_token = encrypted_token
    else:
        user = User(
            vk_id=vk_id,
            encrypted_vk_token=encrypted_token,
            plan=PlanName.BASE,
            plan_expires_at=datetime.now(UTC) + timedelta(days=14),
            daily_likes_limit=base_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=base_plan_limits["daily_add_friends_limit"]
        )
        db.add(user)

    if str(vk_id) == settings.ADMIN_VK_ID:
        admin_limits = get_limits_for_plan(PlanName.PRO)
        user.is_admin = True
        user.plan = PlanName.PRO
        user.plan_expires_at = None
        user.daily_likes_limit = admin_limits["daily_likes_limit"]
        user.daily_add_friends_limit = admin_limits["daily_add_friends_limit"]

    await db.flush()
    await db.refresh(user)

    user_id = user.id

    login_entry = LoginHistory(
        user_id=user_id, # Используем сохраненный ID
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown")
    )
    db.add(login_entry)
    
    await db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Используем сохраненный ID для создания токена
    token_data = {"sub": str(user_id), "profile_id": str(user_id)}
    
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    return EnrichedTokenResponse(
        access_token=access_token,
        token_type="bearer",
        manager_id=user_id,
        active_profile_id=user_id
    )


class SwitchProfileRequest(BaseModel):
    profile_id: int

@router.post("/switch-profile", response_model=EnrichedTokenResponse, summary="Переключиться на другой управляемый профиль")
async def switch_profile(
    request_data: SwitchProfileRequest,
    manager: User = Depends(get_current_manager_user),
    db: AsyncSession = Depends(get_db)
) -> EnrichedTokenResponse:
    
    await db.refresh(manager, attribute_names=["managed_profiles"])
    
    allowed_profile_ids = {p.profile_user_id for p in manager.managed_profiles}
    allowed_profile_ids.add(manager.id)

    if request_data.profile_id not in allowed_profile_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к этому профилю запрещен.")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": str(manager.id),
        "profile_id": str(request_data.profile_id)
    }
    
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    return EnrichedTokenResponse(
        access_token=access_token, 
        token_type="bearer",
        manager_id=manager.id,
        active_profile_id=request_data.profile_id
    )
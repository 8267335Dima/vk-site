# --- backend/app/api/dependencies.py ---
from typing import Annotated, Dict, Any
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.config import settings
from app.db.models import User, ManagedProfile, TeamMember, TeamProfileAccess
from app.db.session import get_db, AsyncSessionFactory
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/vk")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_payload_from_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except (JWTError, ValidationError):
        raise credentials_exception

async def get_current_manager_user(
    payload: Dict[str, Any] = Depends(get_payload_from_token),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Возвращает управляющего пользователя (менеджера) из токена."""
    user_repo = UserRepository(db)
    manager_id_str: str | None = payload.get("sub")
    if manager_id_str is None:
        raise credentials_exception
    
    manager = await user_repo.get(User, int(manager_id_str))
    if manager is None:
        raise credentials_exception
    return manager

async def get_current_active_profile(
    payload: Dict[str, Any] = Depends(get_payload_from_token),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Новая, "умная" зависимость. Проверяет все возможные сценарии доступа.
    """
    logged_in_user_id = int(payload.get("sub"))
    active_profile_id = int(payload.get("profile_id") or logged_in_user_id)

    # Сценарий 1: Пользователь работает со своим собственным профилем
    if logged_in_user_id == active_profile_id:
        profile = await db.get(User, active_profile_id)
        if profile is None: raise credentials_exception
        return profile

    # Сценарий 2: Менеджер работает с одним из своих подключенных профилей
    # Проверяем, является ли logged_in_user менеджером для active_profile_id
    manager_check = await db.execute(
        select(ManagedProfile).where(
            ManagedProfile.manager_user_id == logged_in_user_id,
            ManagedProfile.profile_user_id == active_profile_id
        )
    )
    if manager_check.scalar_one_or_none():
        profile = await db.get(User, active_profile_id)
        if profile is None: raise credentials_exception
        return profile

    # Сценарий 3: Сотрудник команды работает с профилем, к которому ему дали доступ
    member_check_stmt = (
        select(TeamMember)
        .join(TeamProfileAccess)
        .where(
            TeamMember.user_id == logged_in_user_id,
            TeamProfileAccess.profile_user_id == active_profile_id
        )
    )
    member_access = await db.execute(member_check_stmt)
    if member_access.scalar_one_or_none():
        profile = await db.get(User, active_profile_id)
        if profile is None: raise credentials_exception
        return profile
    
    # Если ни одно из условий не выполнено - доступ запрещен
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к этому профилю запрещен.")

async def get_current_user_from_ws(token: str = Query(...)) -> User:
    async with AsyncSessionFactory() as session:
        payload = await get_payload_from_token(token)
        profile_id = int(payload.get("profile_id") or payload.get("sub"))
        user = await session.get(User, profile_id)
        if not user:
            raise credentials_exception
        return user
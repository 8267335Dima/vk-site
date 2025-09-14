# --- backend/app/api/dependencies.py ---
from typing import Annotated, Dict, Any
from fastapi import Depends, HTTPException, Request, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, aliased

from app.core.config import settings
from app.db.models import User, ManagedProfile, TeamMember, TeamProfileAccess
from app.db.session import get_db, AsyncSessionFactory
from app.repositories.user import UserRepository
from fastapi_limiter.depends import RateLimiter


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

# Создаем экземпляр нашего лимитера. Это и есть наша зависимость.
limiter = RateLimiter(times=5, minutes=1, identifier=get_request_identifier)

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

# ИЗМЕНЕНИЕ: Полностью переписанная "умная" зависимость для максимальной производительности
async def get_current_active_profile(
    payload: Dict[str, Any] = Depends(get_payload_from_token),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Новая, "умная" зависимость, оптимизированная для выполнения одного запроса к БД.
    Проверяет все возможные сценарии доступа:
    1. Пользователь работает со своим профилем.
    2. Менеджер работает с управляемым профилем.
    3. Участник команды работает с профилем, к которому ему дали доступ.
    """
    logged_in_user_id = int(payload.get("sub"))
    active_profile_id = int(payload.get("profile_id") or logged_in_user_id)

    # Создаем алиас для TeamMember, чтобы избежать конфликтов в JOIN
    tm_alias = aliased(TeamMember)

    # Единый запрос, который проверяет все условия доступа
    stmt = (
        select(User)
        .outerjoin(ManagedProfile, and_(
            ManagedProfile.manager_user_id == logged_in_user_id,
            ManagedProfile.profile_user_id == User.id
        ))
        .outerjoin(tm_alias, tm_alias.user_id == logged_in_user_id)
        .outerjoin(TeamProfileAccess, and_(
            TeamProfileAccess.team_member_id == tm_alias.id,
            TeamProfileAccess.profile_user_id == User.id
        ))
        .where(
            User.id == active_profile_id,
            (User.id == logged_in_user_id) | # Сценарий 1
            (ManagedProfile.id != None) |     # Сценарий 2
            (TeamProfileAccess.id != None)    # Сценарий 3
        )
    )
    
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile:
        return profile
    
    # Если ни одно из условий не выполнено - доступ запрещен
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к этому профилю запрещен.")


async def get_current_user_from_ws(token: str = Query(...)) -> User:
    async with AsyncSessionFactory() as session:
        payload = await get_payload_from_token(token)
        # На WS нам нужен только активный профиль, полная проверка прав излишня
        profile_id = int(payload.get("profile_id") or payload.get("sub"))
        user = await session.get(User, profile_id)
        if not user:
            raise credentials_exception
        return user
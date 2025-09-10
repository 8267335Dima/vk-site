# backend/app/api/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
# --- ИСПРАВЛЕНИЕ: опечатка pantic -> pydantic ---
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db, AsyncSessionFactory
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/vk")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_user_from_token(token: str, db: AsyncSession) -> User:
    """Общая логика извлечения пользователя из токена."""
    user_repo = UserRepository(db)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValidationError, ValueError):
        raise credentials_exception
    
    user = await user_repo.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
) -> User:
    """Зависимость для HTTP-запросов."""
    return await get_user_from_token(token, db)

async def get_current_user_from_ws(token: str = Query(...)) -> User:
    """
    Зависимость для аутентификации WebSocket-соединений.
    Создает собственную сессию БД, т.к. Depends(get_db) не работает в WS.
    """
    async with AsyncSessionFactory() as session:
        return await get_user_from_token(token, session)

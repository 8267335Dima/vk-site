# backend/app/admin/auth.py

from sqladmin.authentication import AuthenticationBackend
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.core.config import settings
from app.db.models import User

class AdminAuth(AuthenticationBackend):
    def __init__(self, secret_key: str):
        super().__init__(secret_key=secret_key)
        self.secret_key = secret_key

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        if username != settings.ADMIN_USER or password != settings.ADMIN_PASSWORD:
            return False
        
        session: AsyncSession = request.state.session
        
        stmt = select(User).where(User.vk_id == int(settings.ADMIN_VK_ID))
        result = await session.execute(stmt)
        admin_user = result.scalar_one_or_none()
        
        if not admin_user or not admin_user.is_admin:
            return False

        token_payload = {"sub": settings.ADMIN_USER, "scope": "admin_access"}
        token = jwt.encode(token_payload, self.secret_key, algorithm=settings.ALGORITHM)
        request.session.update({"token": token})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        token = request.session.get("token")

        if not token:
            return False

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[settings.ALGORITHM])
            if payload.get("scope") != "admin_access":
                return False
            return True
        except jwt.PyJWTError:
            return False
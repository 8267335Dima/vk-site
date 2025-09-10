# backend/app/repositories/user.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_vk_id(self, vk_id: int) -> User | None:
        """Ищет пользователя по его VK ID."""
        query = select(User).where(User.vk_id == vk_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        """Создает нового пользователя."""
        new_user = User(**user_data)
        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)
        return new_user

    async def update(self, user: User, update_data: dict) -> User:
        """Обновляет данные пользователя."""
        for key, value in update_data.items():
            setattr(user, key, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user
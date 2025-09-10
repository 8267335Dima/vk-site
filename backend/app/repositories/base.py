# backend/app/repositories/base.py
from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository:
    """
    Базовый класс для всех репозиториев.
    Предоставляет общую зависимость от сессии базы данных.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, model, item_id: int):
        """
        Универсальный метод для получения объекта по его ID.
        """
        return await self.session.get(model, item_id)
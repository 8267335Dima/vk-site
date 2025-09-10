# backend/app/repositories/stats.py
import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyStats, User
from app.repositories.base import BaseRepository


class StatsRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_or_create_today_stats(self, user_id: int) -> DailyStats:
        """Получает или создает запись о статистике за сегодня для пользователя."""
        today = datetime.date.today()
        query = select(DailyStats).where(
            DailyStats.user_id == user_id, DailyStats.date == today
        )
        result = await self.session.execute(query)
        stats = result.scalar_one_or_none()

        if not stats:
            stats = DailyStats(user_id=user_id, date=today)
            self.session.add(stats)
            # Важно: коммит здесь не делаем, он будет сделан в конце всей операции в сервисе
            await self.session.flush()
            await self.session.refresh(stats)
        return stats
# backend/app/services/base.py
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.db.models import User, DailyStats, Proxy
from app.services.vk_api import VKAPI
from app.services.humanizer import Humanizer
from app.services.event_emitter import RedisEventEmitter
from app.repositories.stats import StatsRepository
from app.core.security import decrypt_data

class BaseVKService:
    def __init__(
        self,
        db: AsyncSession,
        user: User,
        emitter: RedisEventEmitter,
    ):
        self.db = db
        self.user = user
        self.emitter = emitter
        self.stats_repo = StatsRepository(db)
        self.vk_api: VKAPI | None = None
        self.humanizer: Humanizer | None = None

    async def _initialize_vk_api(self):
        """Асинхронно инициализирует VKAPI и Humanizer."""
        if self.vk_api:
            return

        vk_token = decrypt_data(self.user.encrypted_vk_token)
        proxy_url = await self._get_working_proxy()
        
        self.vk_api = VKAPI(access_token=vk_token, proxy=proxy_url)
        self.humanizer = Humanizer(delay_profile=self.user.delay_profile, logger_func=self.emitter.send_log)

    async def _get_working_proxy(self) -> str | None:
        """
        --- ИЗМЕНЕНИЕ: Получает случайный рабочий прокси из базы данных для пользователя. ---
        """
        # Загружаем связанные прокси, если они еще не загружены
        if 'proxies' not in self.user.__dict__:
             # В редких случаях, когда объект User был получен без 'selectinload',
             # нам нужно будет выполнить явный запрос
             stmt = select(User).where(User.id == self.user.id).options(selectinload(User.proxies))
             result = await self.db.execute(stmt)
             self.user = result.scalar_one()

        working_proxies = [p for p in self.user.proxies if p.is_working]
        if not working_proxies:
            return None
        
        chosen_proxy = random.choice(working_proxies)
        return decrypt_data(chosen_proxy.encrypted_proxy_url)

    async def _get_today_stats(self) -> DailyStats:
        return await self.stats_repo.get_or_create_today_stats(self.user.id)

    async def _increment_stat(self, stats: DailyStats, field_name: str, value: int = 1):
        current_value = getattr(stats, field_name)
        new_value = current_value + value
        setattr(stats, field_name, new_value)
        await self.emitter.send_stats_update(field_name, new_value)

    async def _execute_logic(self, logic_func, *args, **kwargs):
        """
        Обертка для выполнения методов сервиса. Гарантирует инициализацию VK API
        и обработку транзакций.
        """
        await self._initialize_vk_api()
        
        try:
            result = await logic_func(*args, **kwargs)
            await self.db.commit()
            return result
        except Exception as e:
            await self.db.rollback()
            await self.emitter.send_log(f"Произошла ошибка, все изменения отменены: {type(e).__name__} - {e}", status="error")
            raise
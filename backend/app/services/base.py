# --- backend/app/services/base.py ---

import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, DailyStats
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
        """Инициализирует VKAPI клиент и Humanizer, если они еще не созданы."""
        if self.vk_api:
            return

        vk_token = decrypt_data(self.user.encrypted_vk_token)
        proxy_url = await self._get_working_proxy()
        
        self.vk_api = VKAPI(access_token=vk_token, proxy=proxy_url)
        self.humanizer = Humanizer(delay_profile=self.user.delay_profile, logger_func=self.emitter.send_log)

    async def _get_working_proxy(self) -> str | None:
        """Выбирает случайный рабочий прокси из списка пользователя."""
        # Предполагаем, что user.proxies всегда загружены благодаря selectinload в `arq_task_runner`
        working_proxies = [p for p in self.user.proxies if p.is_working]
        if not working_proxies:
            return None
        
        chosen_proxy = random.choice(working_proxies)
        return decrypt_data(chosen_proxy.encrypted_proxy_url)

    async def _get_today_stats(self) -> DailyStats:
        """Получает или создает запись о статистике за сегодня."""
        return await self.stats_repo.get_or_create_today_stats(self.user.id)

    async def _increment_stat(self, stats: DailyStats, field_name: str, value: int = 1):
        """Безопасно увеличивает значение в статистике и отправляет обновление в UI."""
        current_value = getattr(stats, field_name, 0)
        setattr(stats, field_name, current_value + value)
        # Отправляем в UI только новое значение для конкретного поля
        await self.emitter.send_stats_update({f"{field_name}_today": getattr(stats, field_name)})

    async def _execute_logic(self, logic_func, *args, **kwargs):
        """
        Универсальный метод-обертка для выполнения основной логики сервиса.
        Управляет инициализацией, транзакциями и закрытием соединений.
        """
        await self._initialize_vk_api()
        
        try:
            result = await logic_func(*args, **kwargs)
            await self.db.commit()
            return result
        except Exception as e:
            await self.db.rollback()
            # УЛУЧШЕНИЕ: Добавляем больше деталей в лог ошибки
            await self.emitter.send_log(
                f"Произошла критическая ошибка: {type(e).__name__} - {e}. Все изменения отменены.", 
                status="error"
            )
            raise
        finally:
            # УЛУЧШЕНИЕ: Гарантируем закрытие сессии VK API после выполнения
            if self.vk_api:
                await self.vk_api.close()
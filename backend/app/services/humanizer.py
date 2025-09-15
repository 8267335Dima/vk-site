import asyncio
import random
import time
import datetime
from typing import Callable, Awaitable
from app.db.models import DelayProfile

DELAY_CONFIG = {
    DelayProfile.fast: {"base": 0.7, "variation": 0.3, "burst_chance": 0.4},
    DelayProfile.normal: {"base": 1.5, "variation": 0.4, "burst_chance": 0.25},
    DelayProfile.slow: {"base": 3.0, "variation": 0.5, "burst_chance": 0.1},
}

class Humanizer:
    def __init__(self, delay_profile: DelayProfile, logger_func: Callable[..., Awaitable[None]]):
        self.profile = DELAY_CONFIG.get(delay_profile, DELAY_CONFIG[DelayProfile.normal])
        self._log = logger_func
        self.session_start_time = time.time()
        self.actions_in_session = 0
        self.burst_actions_left = 0

    def _get_time_of_day_factor(self) -> float:
        """Возвращает множитель в зависимости от времени суток (имитация 'прайм-тайм')."""
        current_hour = datetime.datetime.now().hour
        if 5 <= current_hour < 10: return 1.1  # Утренняя активность
        if 18 <= current_hour < 23: return 1.25 # Вечерний прайм-тайм
        if 1 <= current_hour < 5: return 0.8   # Ночью действия быстрее
        return 1.0

    def _get_fatigue_factor(self) -> float:
        """Чем дольше сессия, тем выше 'усталость' и медленнее действия."""
        minutes_passed = (time.time() - self.session_start_time) / 60
        fatigue = 1.0 + (self.actions_in_session * 0.007) + (minutes_passed * 0.015)
        return min(fatigue, 1.8)

    async def _sleep(self, base_delay: float):
        self.actions_in_session += 1

        if self.burst_actions_left > 0:
            self.burst_actions_left -= 1
            delay = base_delay * random.uniform(0.2, 0.4)
            await asyncio.sleep(delay)
            return

        fatigue = self._get_fatigue_factor()
        time_factor = self._get_time_of_day_factor()
        variation = self.profile["variation"]
        
        delay = base_delay * fatigue * time_factor * random.uniform(1.0 - variation, 1.0 + variation)

        if random.random() < 0.1: # 10% шанс на длинную паузу (отвлекся на чай)
            hesitation = random.uniform(5.0, 12.0)
            await self._log(f"Имитация отвлечения на {hesitation:.1f} сек.", "debug")
            delay += hesitation

        await self._log(f"Пауза ~{delay:.1f}с (усталость:x{fatigue:.2f}, время:x{time_factor:.2f})", "debug")
        await asyncio.sleep(delay)

    async def think(self, action_type: str):
        """Имитация 'обдумывания' действия перед его выполнением."""
        base_thinking_time = self.profile['base']
        if action_type == 'message': base_thinking_time *= 1.8
        if action_type == 'add_friend': base_thinking_time *= 1.5
        await self._sleep(base_thinking_time)

    async def read_and_scroll(self):
        """Имитация загрузки, скроллинга и чтения контента."""
        await self._sleep(self.profile['base'] * 1.2) # "Загрузка"
        
        scroll_count = random.choices([0, 1, 2, 3, 4], weights=[20, 30, 30, 15, 5], k=1)[0]
        if scroll_count > 0:
            for _ in range(scroll_count):
                await self._sleep(self.profile['base'] * 0.7)
        
        if random.random() < self.profile["burst_chance"]:
            self.burst_actions_left = random.randint(3, 8)
            await self._log(f"Начало 'пакетного' режима на {self.burst_actions_left} действий.", "debug")
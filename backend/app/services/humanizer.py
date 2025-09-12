# backend/app/services/humanizer.py
import asyncio
import random
from typing import Callable, Awaitable
from app.db.models import DelayProfile
import structlog

log = structlog.get_logger(__name__)

DELAY_CONFIG = {
    DelayProfile.fast: {
        "page_load": (0.8, 1.5),
        "scroll": (0.5, 1.2),
        "action_decision": (0.7, 1.3),
        "short_action": (0.6, 1.1),
    },
    DelayProfile.normal: {
        "page_load": (1.5, 3.0),
        "scroll": (1.0, 2.5),
        "action_decision": (1.2, 2.8),
        "short_action": (1.0, 2.0),
    },
    DelayProfile.slow: {
        "page_load": (3.0, 5.5),
        "scroll": (2.5, 4.0),
        "action_decision": (2.8, 5.0),
        "short_action": (2.0, 3.5),
    },
}

class Humanizer:
    def __init__(self, delay_profile: DelayProfile, logger_func: Callable[..., Awaitable[None]]):
        self.profile = DELAY_CONFIG.get(delay_profile, DELAY_CONFIG[DelayProfile.normal])
        self._log = logger_func
        self.session_multiplier = random.uniform(0.9, 1.1)

    async def _sleep(self, min_sec: float, max_sec: float, log_message: str | None = None):
        delay = random.uniform(min_sec, max_sec) * self.session_multiplier
        if log_message:
            await self._log(f"{log_message} (пауза ~{delay:.1f} сек.)", status="debug")
        await asyncio.sleep(delay)

    async def imitate_page_view(self):
        load_min, load_max = self.profile["page_load"]
        await self._sleep(load_min, load_max, "Имитация загрузки страницы...")
        
        if random.random() < 0.7:
            scroll_min, scroll_max = self.profile["scroll"]
            scroll_times = random.randint(1, 4)
            
            if scroll_times > 0:
                await self._log(f"Имитация скроллинга ({scroll_times} раз)...", status="debug")
                for _ in range(scroll_times):
                    await self._sleep(scroll_min * 0.8, scroll_max * 1.2)
            
        decision_min, decision_max = self.profile["action_decision"]
        await self._sleep(decision_min, decision_max, "Пауза перед действием...")

    async def imitate_simple_action(self):
        if random.random() < 0.3:
            await self._sleep(0.3, 0.8)

        action_min, action_max = self.profile["short_action"]
        await self._sleep(action_min, action_max)
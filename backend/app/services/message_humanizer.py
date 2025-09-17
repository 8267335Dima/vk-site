# --- backend/app/services/message_humanizer.py ---
import asyncio
import random
import structlog
from typing import List, Dict, Any, Literal, Optional
from app.services.vk_api import VKAPI, VKAccessDeniedError
from app.services.event_emitter import RedisEventEmitter

log = structlog.get_logger(__name__)

# Настройки скоростей "печати" (символов в минуту) и вариативности
SPEED_PROFILES = {
    "slow": {"cpm": 300, "variation": 0.3, "base_delay": 2.5},
    "normal": {"cpm": 600, "variation": 0.25, "base_delay": 1.5},
    "fast": {"cpm": 900, "variation": 0.2, "base_delay": 0.8},
}

SpeedProfile = Literal["slow", "normal", "fast"]

class MessageHumanizer:
    """
    Обеспечивает последовательную отправку сообщений с имитацией
    человеческого поведения: задержками, "прочтением" диалога и "набором" текста.
    """
    def __init__(self, vk_api: VKAPI, emitter: RedisEventEmitter):
        self.vk_api = vk_api
        self.emitter = emitter

    async def send_messages_sequentially(
        self,
        targets: List[Dict[str, Any]],
        message_template: str,
        attachments: Optional[str] = None, # <-- ИЗМЕНЕНИЕ: Принимает готовую строку вложений
        speed: SpeedProfile = "normal",
        simulate_typing: bool = True
    ) -> int:
        """
        Отправляет сообщения каждому получателю из списка по очереди.

        :param targets: Список словарей с информацией о получателях.
        :param message_template: Шаблон сообщения, поддерживает {name}.
        :param attachments: Строка с ID вложений (напр. 'photo123_456,photo123_789').
        :param speed: Профиль скорости отправки.
        :param simulate_typing: Включать ли имитацию набора текста.
        :return: Количество успешно отправленных сообщений.
        """
        profile = SPEED_PROFILES.get(speed, SPEED_PROFILES["normal"])
        successful_sends = 0

        for target in targets:
            target_id = target.get('id')
            if not target_id:
                continue

            first_name = target.get('first_name', '')
            full_name = f"{first_name} {target.get('last_name', '')}"
            url = f"https://vk.com/id{target_id}"
            
            final_message = message_template.replace("{name}", first_name)
            
            try:
                # 1. Имитация "открытия и прочтения" диалога
                # --- ИСПРАВЛЕНИЕ: Удалена строка `await self.vk_api.messages.markAsRead(peer_id=target_id)`, вызывавшая ошибку ---
                await asyncio.sleep(random.uniform(0.5, 1.2))

                # 2. Расчет задержки и имитация набора текста
                if simulate_typing:
                    typing_duration = (len(final_message) / (profile["cpm"] / 60)) 
                    variation = profile["variation"]
                    total_delay = typing_duration * random.uniform(1 - variation, 1 + variation)
                    
                    await asyncio.sleep(profile["base_delay"] * random.uniform(0.8, 1.2))
                    
                    await self.emitter.send_log(f"Имитация набора текста для {full_name} (~{total_delay:.1f} сек)...", "debug")
                    await self.vk_api.messages.setActivity(user_id=target_id, type='typing')
                    await asyncio.sleep(total_delay)

                # 3. Отправка сообщения с вложениями
                if await self.vk_api.messages.send(target_id, final_message, attachment=attachments):
                    successful_sends += 1
                    await self.emitter.send_log(f"Сообщение для {full_name} успешно отправлено.", "success", target_url=url)
                else:
                    await self.emitter.send_log(f"Не удалось отправить сообщение для {full_name}.", "error", target_url=url)

            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить (профиль закрыт или ЧС): {full_name}", "warning", target_url=url)
            except Exception as e:
                log.error("message_humanizer.error", user_id=self.emitter.user_id, error=str(e))
                await self.emitter.send_log(f"Ошибка при отправке сообщения для {full_name}: {e}", "error", target_url=url)
            
            # 4. Финальная задержка перед переходом к следующему диалогу
            await asyncio.sleep(profile["base_delay"] * random.uniform(1.5, 2.5))

        return successful_sends
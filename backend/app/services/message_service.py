# backend/app/services/message_service.py
from typing import Dict, Any, List
import random
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError, InvalidActionSettingsError
from app.services.vk_api import VKAccessDeniedError

class MessageService(BaseVKService):

    async def send_mass_message(self, count: int, filters: Dict[str, Any], message_text: str, only_new_dialogs: bool):
        """Обертка для запуска логики массовой рассылки."""
        return await self._execute_logic(self._send_mass_message_logic, count, filters, message_text, only_new_dialogs)

    async def _send_mass_message_logic(self, count: int, filters: Dict[str, Any], message_text: str, only_new_dialogs: bool):
        """Основная логика для массовой отправки сообщений друзьям."""
        if not message_text or not message_text.strip():
            raise InvalidActionSettingsError("Текст сообщения не может быть пустым.")

        await self.emitter.send_log(f"Запуск массовой рассылки. Цель: {count} сообщений.", "info")
        stats = await self._get_today_stats()

        # 1. Получаем и фильтруем друзей
        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen")
        if not friends_response:
            await self.emitter.send_log("Не удалось получить список друзей.", "error")
            return

        filtered_friends = self._apply_filters_to_profiles(friends_response, filters)
        if not filtered_friends:
            await self.emitter.send_log("После применения фильтров не осталось друзей для рассылки.", "warning")
            return

        await self.emitter.send_log(f"Найдено друзей по фильтрам: {len(filtered_friends)}. Начинаем обработку.", "info")
        random.shuffle(filtered_friends)
        
        # 2. Фильтруем по диалогам, если требуется
        target_friends = []
        if only_new_dialogs:
            dialogs = await self.vk_api.get_conversations(count=200)
            dialog_peer_ids = {conv['conversation']['peer']['id'] for conv in dialogs.get('items', [])}
            target_friends = [f for f in filtered_friends if f['id'] not in dialog_peer_ids]
            await self.emitter.send_log(f"Режим 'Только новые диалоги'. Осталось целей: {len(target_friends)}.", "info")
        else:
            target_friends = filtered_friends
        
        if not target_friends:
            await self.emitter.send_log("Не найдено подходящих получателей.", "success")
            return
            
        # 3. Отправляем сообщения
        processed_count = 0
        for friend in target_friends:
            if processed_count >= count:
                break

            friend_id = friend['id']
            name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
            url = f"https://vk.com/id{friend_id}"
            
            # Заменяем плейсхолдер имени
            final_message = message_text.replace("{name}", friend.get('first_name', ''))

            await self.humanizer.imitate_page_view()

            try:
                result = await self.vk_api.send_message(friend_id, final_message)
                if result:
                    processed_count += 1
                    await self._increment_stat(stats, 'messages_sent_count')
                    await self.emitter.send_log(f"Сообщение для {name} успешно отправлено.", "success", target_url=url)
                else:
                    await self.emitter.send_log(f"Не удалось отправить сообщение для {name}. Ответ VK: {result}", "error", target_url=url)
            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить сообщение (профиль закрыт или ЧС): {name}", "warning", target_url=url)
            except Exception as e:
                await self.emitter.send_log(f"Ошибка при отправке сообщения для {name}: {e}", "error", target_url=url)

        await self.emitter.send_log(f"Рассылка завершена. Отправлено сообщений: {processed_count}.", "success")

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Эта функция-фильтр может быть вынесена в базовый класс или утилиты, если используется в нескольких сервисах
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()

        for profile in profiles:
            if filters.get('sex') is not None and filters.get('sex') != 0 and profile.get('sex') != filters['sex']:
                continue
            if filters.get('is_online', False) and not profile.get('online', 0):
                continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts:
                last_seen_hours = filters.get('last_seen_hours')
                if last_seen_hours and (now_ts - last_seen_ts) > (last_seen_hours * 3600):
                    continue
            
            filtered_profiles.append(profile)
        return filtered_profiles
# backend/app/services/message_service.py
import random
from app.services.base import BaseVKService
from app.core.exceptions import InvalidActionSettingsError
from app.services.vk_api import VKAccessDeniedError
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import MassMessagingRequest

class MessageService(BaseVKService):

    async def send_mass_message(self, params: MassMessagingRequest):
        return await self._execute_logic(self._send_mass_message_logic, params)

    async def _send_mass_message_logic(self, params: MassMessagingRequest):
        if not params.message_text or not params.message_text.strip():
            raise InvalidActionSettingsError("Текст сообщения не может быть пустым.")

        await self.emitter.send_log(f"Запуск массовой рассылки. Цель: {params.count} сообщений.", "info")
        stats = await self._get_today_stats()

        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,status")
        if not friends_response:
            await self.emitter.send_log("Не удалось получить список друзей.", "error")
            return

        filtered_friends = apply_filters_to_profiles(friends_response, params.filters)
        if not filtered_friends:
            await self.emitter.send_log("После применения фильтров не осталось друзей для рассылки.", "warning")
            return

        await self.emitter.send_log(f"Найдено друзей по фильтрам: {len(filtered_friends)}. Начинаем обработку.", "info")
        random.shuffle(filtered_friends)
        
        target_friends = filtered_friends
        if params.only_new_dialogs:
            dialogs = await self.vk_api.get_conversations(count=200)
            dialog_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in dialogs.get('items', [])}
            target_friends = [f for f in filtered_friends if f.get('id') not in dialog_peer_ids]
            await self.emitter.send_log(f"Режим 'Только новые диалоги'. Осталось целей: {len(target_friends)}.", "info")
        
        if not target_friends:
            await self.emitter.send_log("Не найдено подходящих получателей.", "success")
            return
            
        processed_count = 0
        for friend in target_friends:
            if processed_count >= params.count:
                break

            friend_id = friend.get('id')
            name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
            url = f"https://vk.com/id{friend_id}"
            
            final_message = params.message_text.replace("{name}", friend.get('first_name', ''))

            await self.humanizer.imitate_page_view()

            try:
                if await self.vk_api.send_message(friend_id, final_message):
                    processed_count += 1
                    await self._increment_stat(stats, 'messages_sent_count')
                    await self.emitter.send_log(f"Сообщение для {name} успешно отправлено.", "success", target_url=url)
                else:
                    await self.emitter.send_log(f"Не удалось отправить сообщение для {name}.", "error", target_url=url)
            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить сообщение (профиль закрыт или ЧС): {name}", "warning", target_url=url)
            except Exception as e:
                await self.emitter.send_log(f"Ошибка при отправке сообщения для {name}: {e}", "error", target_url=url)

        await self.emitter.send_log(f"Рассылка завершена. Отправлено сообщений: {processed_count}.", "success")
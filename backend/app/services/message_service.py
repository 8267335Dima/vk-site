# --- backend/app/services/message_service.py ---
import random
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.core.exceptions import InvalidActionSettingsError, UserLimitReachedError
from app.services.vk_api import VKAccessDeniedError
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import MassMessagingRequest
from app.services.message_humanizer import MessageHumanizer


class MessageService(BaseVKService):

    async def filter_targets_by_conversation_status(
        self,
        targets: List[Dict[str, Any]],
        only_new_dialogs: bool,
        only_unread: bool
    ) -> List[Dict[str, Any]]:
        """
        Фильтрует список целей на основе статуса их диалога с пользователем.
        """
        if only_new_dialogs and only_unread:
            raise InvalidActionSettingsError("Нельзя одновременно использовать 'Только новые диалоги' и 'Только непрочитанные'.")

        final_targets = list(targets) 

        if only_new_dialogs:
            await self.emitter.send_log("Применяем фильтр: 'Только новые диалоги'...", "info")
            dialogs = await self.vk_api.get_conversations(count=200)
            dialog_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in dialogs.get('items', [])}
            final_targets = [t for t in targets if t.get('id') not in dialog_peer_ids]

        if only_unread:
            await self.emitter.send_log("Применяем фильтр: 'Только непрочитанные'...", "info")
            unread_convs = await self.vk_api.get_conversations(count=200, filter='unread')
            if not unread_convs or not unread_convs.get('items'):
                return []
            unread_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in unread_convs.get('items', [])}
            final_targets = [t for t in targets if t.get('id') in unread_peer_ids]
            
        return final_targets

    async def get_mass_messaging_targets(self, params: MassMessagingRequest) -> List[Dict[str, Any]]:
        """Вспомогательный метод для получения и фильтрации целей для МАССОВОЙ РАССЫЛКИ."""
        # <<< ИСПРАВЛЕНИЕ ЗДЕСЬ >>>
        response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,status,is_closed,city")
        
        if not response or not response.get('items'):
            return []
        
        # Итерируемся по response.get('items', []), а не по всему ответу
        friends_list = [f for f in response.get('items', []) if f.get('id') != self.user.vk_id]

        filtered_friends = await apply_filters_to_profiles(friends_list, params.filters)
        
        targets = await self.filter_targets_by_conversation_status(
            filtered_friends, params.only_new_dialogs, params.only_unread
        )
            
        return targets

    async def send_mass_message(self, params: MassMessagingRequest):
         return await self._execute_logic(self._send_mass_message_logic, params)

    async def _send_mass_message_logic(self, params: MassMessagingRequest):
        if not params.message_text or not params.message_text.strip():
            raise InvalidActionSettingsError("Текст сообщения не может быть пустым.")
        
        attachments_str = ",".join(params.attachments) if params.attachments else None

        await self.emitter.send_log(f"Запуск массовой рассылки. Цель: {params.count} сообщений.", "info")
        stats = await self._get_today_stats()
        if self.user.daily_message_limit <= 0:
            raise UserLimitReachedError(f"Достигнут дневной лимит сообщений ({self.user.daily_message_limit}).")

        target_friends = await self.get_mass_messaging_targets(params)

        if not target_friends:
            await self.emitter.send_log("Не найдено подходящих получателей по заданным фильтрам.", "success")
            return
            
        await self.emitter.send_log(f"Найдено получателей по фильтрам: {len(target_friends)}. Начинаем отправку.", "info")
        random.shuffle(target_friends)
        
        targets_to_process = target_friends[:params.count]
        processed_count = 0
        
        if params.humanized_sending.enabled:
            await self.emitter.send_log("Активирован режим 'человечной' отправки.", "info")
            humanizer = MessageHumanizer(self.vk_api, self.emitter)
            
            for target in targets_to_process:
                # Вторичная проверка внутри цикла на случай, если лимит закончился во время работы
                if stats.messages_sent_count >= self.user.daily_message_limit:
                    await self.emitter.send_log(f"Дневной лимит сообщений ({self.user.daily_message_limit}) был достигнут во время рассылки.", "warning")
                    break # Выходим из цикла, а не бросаем ошибку
                
                sent_count = await humanizer.send_messages_sequentially(
                    targets=[target],
                    message_template=params.message_text,
                    attachments=attachments_str,
                    speed=params.humanized_sending.speed,
                    simulate_typing=params.humanized_sending.simulate_typing
                )
                if sent_count > 0:
                    processed_count += 1
                    await self._increment_stat(stats, 'messages_sent_count')

        else: # Быстрая пакетная отправка
            for friend in targets_to_process:
                if stats.messages_sent_count >= self.user.daily_message_limit:
                    await self.emitter.send_log(f"Дневной лимит сообщений ({self.user.daily_message_limit}) был достигнут во время рассылки.", "warning")
                    break

                friend_id = friend.get('id')
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/id{friend_id}"
                
                final_message = params.message_text.replace("{name}", friend.get('first_name', ''))
                await self.humanizer.think(action_type='message')

                try:
                    if await self.vk_api.messages.send(friend_id, final_message, attachment=attachments_str):
                        processed_count += 1
                        await self._increment_stat(stats, 'messages_sent_count')
                        await self.emitter.send_log(f"Сообщение для {name} успешно отправлено.", "success", target_url=url)
                except VKAccessDeniedError:
                    await self.emitter.send_log(f"Не удалось отправить (профиль закрыт или ЧС): {name}", "warning", target_url=url)
        
        await self.emitter.send_log(f"Рассылка завершена. Отправлено сообщений: {processed_count}.", "success")
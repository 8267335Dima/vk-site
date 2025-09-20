import random
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.core.exceptions import InvalidActionSettingsError, UserLimitReachedError
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import MassMessagingRequest
from app.services.message_humanizer import MessageHumanizer
from .interfaces import IExecutableTask, IPreviewableTask

class MessageService(BaseVKService, IExecutableTask, IPreviewableTask):
    async def get_targets(self, params: MassMessagingRequest) -> List[Dict[str, Any]]:
        await self._initialize_vk_api()
        response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,status,is_closed,city")
        if not response or not response.get('items'):
            return []
        friends_list = [f for f in response.get('items', []) if f.get('id') != self.user.vk_id]
        filtered_friends = await apply_filters_to_profiles(friends_list, params.filters)
        return await self.filter_targets_by_conversation_status(
            filtered_friends, params.only_new_dialogs, params.only_unread
        )
    
    async def execute(self, params: MassMessagingRequest) -> str:
        await self._initialize_vk_api()
        if not params.message_text or not params.message_text.strip():
            raise InvalidActionSettingsError("Текст сообщения не может быть пустым.")
        stats = await self._get_today_stats()
        if self.user.daily_message_limit <= 0:
            raise UserLimitReachedError(f"Достигнут дневной лимит сообщений ({self.user.daily_message_limit}).")
        target_friends = await self.get_targets(params)
        if not target_friends:
            return "Не найдено подходящих получателей по заданным фильтрам."
        random.shuffle(target_friends)
        targets_to_process = target_friends[:params.count]
        processed_count = 0
        attachments_str = ",".join(params.attachments) if params.attachments else None
        humanizer = MessageHumanizer(self.vk_api, self.emitter)
        for target in targets_to_process:
            if stats.messages_sent_count >= self.user.daily_message_limit:
                break
            sent_count = await humanizer.send_messages_sequentially(
                targets=[target], message_template=params.message_text, attachments=attachments_str,
                speed=params.humanized_sending.speed, simulate_typing=params.humanized_sending.simulate_typing
            )
            if sent_count > 0:
                processed_count += 1
                await self._increment_stat(stats, 'messages_sent_count')
        return f"Рассылка завершена. Отправлено сообщений: {processed_count}."
    
    async def filter_targets_by_conversation_status(self, targets, only_new, only_unread):
        if only_new and only_unread:
            raise InvalidActionSettingsError("Нельзя одновременно использовать 'Только новые диалоги' и 'Только непрочитанные'.")
        if not only_new and not only_unread: return targets
        if only_new:
            dialogs = await self.vk_api.get_conversations(count=200)
            if not dialogs or not dialogs.get('items'): return targets
            dialog_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in dialogs.get('items', [])}
            return [t for t in targets if t.get('id') not in dialog_peer_ids]
        if only_unread:
            unread_convs = await self.vk_api.get_conversations(count=200, filter='unread')
            if not unread_convs or not unread_convs.get('items'): return []
            unread_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in unread_convs.get('items', [])}
            return [t for t in targets if t.get('id') in unread_peer_ids]
        return targets
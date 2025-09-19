# backend/app/services/ai_message_service.py
from app.services.base import BaseVKService
from app.db.models import User
from app.ai.unified_service import UnifiedAIService
from app.services.message_humanizer import MessageHumanizer
from app.core.security import decrypt_data
from app.core.exceptions import UserActionException

class AIMessageService(BaseVKService):

    async def _initialize_ai_service(self) -> UnifiedAIService:
        """Инициализирует ИИ-сервис на основе настроек пользователя."""
        api_key = decrypt_data(self.user.encrypted_ai_api_key)
        if not (self.user.ai_provider and api_key and self.user.ai_model_name):
            raise UserActionException("Настройки ИИ не сконфигурированы.")
        
        return UnifiedAIService(
            provider=self.user.ai_provider,
            api_key=api_key,
            model=self.user.ai_model_name
        )

    async def process_unanswered_conversations(self, params: dict):
        """Обрабатывает непрочитанные диалоги с помощью ИИ."""
        await self._initialize_vk_api()
        ai_service = await self._initialize_ai_service()
        
        response = await self.vk_api.messages.getConversations(filter='unanswered', count=params.get('count', 10))
        if not response or not response.get('items'):
            await self.emitter.send_log("Новых диалогов для ИИ-ответа не найдено.", "info")
            return
            
        system_prompt = self.user.ai_system_prompt or "Отвечай кратко и по делу."
        
        for conv in response['items']:
            peer_id = conv.get('conversation', {}).get('peer', {}).get('id')
            if not peer_id: continue

            history_response = await self.vk_api.messages.getHistory(user_id=peer_id, count=20)
            if not history_response or not history_response.get('items'): continue
            
            messages = history_response['items']
            last_user_message = next((m['text'] for m in reversed(messages) if m['from_id'] == peer_id), None)
            if not last_user_message: continue

            message_history = []
            for msg in reversed(messages[1:]):
                role = "user" if msg['from_id'] == peer_id else "assistant"
                message_history.append({"role": role, "content": msg['text']})

            ai_response = await ai_service.get_response(
                system_prompt=system_prompt,
                message_history=message_history,
                user_input=last_user_message
            )

            humanizer = MessageHumanizer(self.vk_api, self.emitter)
            await humanizer.send_messages_sequentially(
                targets=[{"id": peer_id}], message_template=ai_response,
                speed="normal", simulate_typing=True
            )
            await self.vk_api.messages.markAsRead(peer_id=peer_id)
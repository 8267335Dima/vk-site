# backend/app/services/ai_message_service.py

from app.services.base import BaseVKService
from app.ai.unified_service import UnifiedAIService
from app.services.message_humanizer import MessageHumanizer
from app.core.security import decrypt_data
from app.core.exceptions import UserActionException
from typing import List, Dict, Any, Union
import json

class AIMessageService(BaseVKService):

    async def _initialize_ai_service(self) -> UnifiedAIService:
        """Инициализирует ИИ-сервис на основе настроек пользователя."""
        api_key = decrypt_data(self.user.encrypted_ai_api_key)
        fallback = self.user.ai_fallback_message or "Извините, в данный момент не могу ответить."
        
        if not all([self.user.ai_provider, api_key, self.user.ai_model_name]):
            raise UserActionException("Настройки ИИ не сконфигурированы.")
        
        return UnifiedAIService(
            provider=self.user.ai_provider,
            api_key=api_key,
            model=self.user.ai_model_name,
            fallback_message=fallback
        )
    
    # --- НОВЫЙ, БОЛЕЕ КАЧЕСТВЕННЫЙ МЕТОД ---
    def _parse_attachments(self, attachments: List[Dict[str, Any]]) -> tuple[list, list]:
        """
        Извлекает URL изображений/стикеров и текстовые описания из вложений VK.
        Возвращает кортеж: (описания_текстом, медиа_объекты_для_ai).
        """
        image_objects = []
        text_descriptions = []
        wall_ids_to_fetch = []

        for att in attachments:
            att_type = att.get("type")
            if att_type == "photo" and "photo" in att:
                sizes = att["photo"].get("sizes", [])
                if sizes:
                    best_photo = max(sizes, key=lambda s: s.get("height", 0))
                    image_objects.append({"type": "image_url", "image_url": {"url": best_photo["url"]}})
            elif att_type == "sticker" and "sticker" in att:
                images = att["sticker"].get("images", [])
                if images:
                    best_sticker = max(images, key=lambda s: s.get("height", 0))
                    image_objects.append({"type": "image_url", "image_url": {"url": best_sticker["url"]}})
            elif att_type == "wall" and "wall" in att:
                owner_id = att['wall'].get('owner_id') or att['wall'].get('from_id')
                post_id = att['wall'].get('id')
                if owner_id and post_id:
                    wall_ids_to_fetch.append(f"{owner_id}_{post_id}")
            elif att_type == "doc":
                text_descriptions.append(f"[Вложение: документ '{att.get('doc', {}).get('title', 'Без названия')}']")
            elif att_type == "audio_message":
                 text_descriptions.append("[Вложение: голосовое сообщение]")
            elif att_type == "video":
                text_descriptions.append("[Вложение: видео]")
            elif att_type == "audio":
                text_descriptions.append("[Вложение: аудиозапись]")

        return text_descriptions, image_objects, wall_ids_to_fetch

    # --- ИЗМЕНЕНИЕ: ЛОГИКА СБОРА КОНТЕКСТА С ПАКЕТНЫМ ЗАПРОСОМ ---
    async def _build_context_from_history(self, messages: List[Dict[str, Any]], own_vk_id: int) -> List[Dict[str, Any]]:
        """
        Создает историю сообщений для модели, эффективно извлекая контент из вложений.
        """
        history = []
        all_wall_ids = set()
        wall_placeholders = {} # Для связи ID поста с сообщением

        # Первый проход: собираем все ID пересланных сообщений
        for i, msg in enumerate(messages):
            if msg.get("attachments"):
                _, _, wall_ids = self._parse_attachments(msg["attachments"])
                if wall_ids:
                    all_wall_ids.update(wall_ids)
                    wall_placeholders[i] = wall_ids

        # Пакетный запрос для получения текста всех пересланных сообщений
        wall_contents = {}
        if all_wall_ids:
            posts_str = ",".join(list(all_wall_ids))
            wall_data = await self.vk_api.wall.getById(posts=posts_str)
            if wall_data:
                wall_contents = {f"{post['owner_id']}_{post['id']}": post.get('text', '[пустой пост]') for post in wall_data}

        # Второй проход: формируем историю для AI
        for i, msg in enumerate(reversed(messages)):
            role = "assistant" if msg['from_id'] == own_vk_id else "user"
            text_content = msg.get('text', '')
            
            content_parts = []

            if msg.get("attachments"):
                text_descs, image_objs, _ = self._parse_attachments(msg["attachments"])
                
                # Добавляем текстовые описания вложений
                if text_descs:
                    text_content = f"{' '.join(text_descs)} {text_content}".strip()
                
                # Добавляем контент пересланных сообщений
                if i in wall_placeholders:
                    forwarded_texts = [wall_contents.get(wall_id, '') for wall_id in wall_placeholders[i]]
                    forwarded_full_text = "\n".join(f"[Пересланное сообщение]: {text}" for text in forwarded_texts if text)
                    text_content = f"{text_content}\n{forwarded_full_text}".strip()

                # Собираем все в мультимодальный формат
                if text_content:
                    content_parts.append({"type": "text", "text": text_content})
                content_parts.extend(image_objs)

            else: # Если вложений нет, только текст
                if text_content:
                    content_parts.append({"type": "text", "text": text_content})

            if content_parts:
                history.append({"role": role, "content": content_parts if len(content_parts) > 1 else content_parts[0]['text']})

        return history


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

            history_response = await self.vk_api.messages.getHistory(user_id=peer_id, count=20, extended=1)
            if not history_response or not history_response.get('items'): continue
            
            messages = history_response['items']
            last_message = messages[0] if messages else None
            if not last_message or last_message['from_id'] == self.user.vk_id:
                continue

            # Собираем контекст из всей истории, включая последнее сообщение
            message_context = self._build_context_from_history(messages, self.user.vk_id)
            if not message_context:
                continue
                
            # Последнее сообщение пользователя для get_response
            last_user_input = message_context[-1]['content']
            # Вся предыдущая история
            previous_history = message_context[:-1]

            # Извлекаем изображения из последнего сообщения для передачи в get_response
            images_from_last_message = []
            if isinstance(last_user_input, list):
                text_part = ""
                for part in last_user_input:
                    if part['type'] == 'text':
                        text_part += part['text']
                    elif part['type'] == 'image_url':
                        images_from_last_message.append(part['image_url'])
                last_user_input = text_part.strip()

            ai_response_text = await ai_service.get_response(
                system_prompt=system_prompt,
                message_history=previous_history,
                user_input=last_user_input,
                images=images_from_last_message
            )

            humanizer = MessageHumanizer(self.vk_api, self.emitter)
            await humanizer.send_messages_sequentially(
                targets=[{"id": peer_id}], message_template=ai_response_text
            )
            await self.vk_api.messages.markAsRead(peer_id=peer_id)
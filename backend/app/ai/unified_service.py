# backend/app/ai/unified_service.py
from openai import AsyncOpenAI, APIError
from typing import List, Dict, Literal, Optional
import structlog

from app.core.exceptions import UserActionException

log = structlog.get_logger(__name__)

AIProvider = Literal["openai", "google"]

# Конфигурация базовых URL для провайдеров
PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
}

class UnifiedAIService:
    """
    Унифицированный сервис для работы с различными LLM через OpenAI-совместимый клиент.
    """
    def __init__(self, provider: AIProvider, api_key: str, model: str, fallback_message: str):
        if provider not in PROVIDER_BASE_URLS:
            raise UserActionException(f"Провайдер ИИ '{provider}' не поддерживается.")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=PROVIDER_BASE_URLS[provider]
        )
        self.model = model
        self.provider = provider
        self.fallback_message = fallback_message

    async def get_response(
        self,
        system_prompt: str,
        message_history: List[Dict[str, str]],
        user_input: str,
        image_url: Optional[str] = None
    ) -> str:
        """
        Генерирует ответ от LLM, опционально с анализом изображения по URL.
        """
        user_content: any = user_input
        if image_url:
            user_content = [
                {"type": "text", "text": user_input},
                {
                    "type": "image_url",
                    "image_url": {"url": image_url},
                },
            ]

        messages = [
            {"role": "system", "content": system_prompt},
            *message_history,
            {"role": "user", "content": user_content}
        ]
        
        model_path = f"models/{self.model}" if self.provider == "google" else self.model

        try:
            completion = await self.client.chat.completions.create(
                model=model_path,
                messages=messages,
            )
            response = completion.choices[0].message.content
            # ИЗМЕНЕНИЕ: Используем заглушку, если ответ пустой
            return response.strip() if response else self.fallback_message
        except APIError as e:
            log.error("ai.service.api_error", provider=self.provider, model=self.model, status_code=e.status_code, error=e.message)
            # ИЗМЕНЕНИЕ: Возвращаем заглушку при ошибке API
            return self.fallback_message
        except Exception as e:
            log.error("ai.service.unknown_error", provider=self.provider, model=self.model, error=str(e))
            # ИЗМЕНЕНИЕ: Возвращаем заглушку при любой другой ошибке
            return self.fallback_message
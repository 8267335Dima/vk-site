# backend/app/ai/unified_service.py
from openai import AsyncOpenAI, APIError
from typing import List, Dict, Literal, Optional, Union
import structlog

from app.core.exceptions import UserActionException

log = structlog.get_logger(__name__)

AIProvider = Literal["openai", "google"]

# Конфигурация базовых URL для провайдеров
PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai/",
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
        images: Optional[List[Union[str, Dict[str, str]]]] = None,
    ) -> str:
        """
        Генерирует ответ от LLM, с поддержкой нескольких изображений.
        images: список URL или объектов {"url": "..."} либо {"data": "...", "format": "..."} (base64).
        """
        user_content: Union[str, list] = user_input

        if images:
            user_content = [{"type": "text", "text": user_input}]
            for img in images:
                if isinstance(img, str):  # если просто URL
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": img},
                    })
                elif isinstance(img, dict):  # base64 или расширенный формат
                    if "url" in img:
                        user_content.append({
                            "type": "image_url",
                            "image_url": {"url": img["url"]},
                        })
                    elif "data" in img and "format" in img:
                        user_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{img['format']};base64,{img['data']}"
                            },
                        })

        messages = [
            {"role": "system", "content": system_prompt},
            *message_history,
            {"role": "user", "content": user_content},
        ]

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            response = completion.choices[0].message.content
            return response.strip() if response else self.fallback_message

        except APIError as e:
            log.error(
                "ai.service.api_error",
                provider=self.provider,
                model=self.model,
                status_code=e.status_code,
                error=e.message,
            )
            return self.fallback_message

        except Exception as e:
            log.error(
                "ai.service.unknown_error",
                provider=self.provider,
                model=self.model,
                error=str(e),
            )
            return self.fallback_message

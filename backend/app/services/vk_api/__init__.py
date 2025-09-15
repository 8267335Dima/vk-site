# --- backend/app/services/vk_api/__init__.py ---

import aiohttp
import json
import asyncio
from typing import Optional, Dict, Any, List

from app.core.config import settings

# Экспортируем исключения для удобного доступа
from .base import VKAPIError, VKAuthError, VKAccessDeniedError, VKFloodControlError, VKCaptchaError, ERROR_CODE_MAP

# Импортируем все разделы API
from .account import AccountAPI
from .friends import FriendsAPI
from .groups import GroupsAPI
from .likes import LikesAPI
from .messages import MessagesAPI
from .newsfeed import NewsfeedAPI
from .photos import PhotosAPI
from .stories import StoriesAPI
from .users import UsersAPI
from .wall import WallAPI


class VKAPI:
    """
    Основной класс-фасад для взаимодействия с VK API.
    Предоставляет доступ к логическим разделам API через свои атрибуты.
    Пример: `vk_api.friends.get(...)`
    
    ИЗМЕНЕНИЕ: Класс теперь управляет жизненным циклом одного aiohttp.ClientSession
    для повышения производительности за счет переиспользования соединений.
    """
    def __init__(self, access_token: str, proxy: Optional[str] = None):
        self.access_token = access_token
        self.proxy = proxy
        self.api_version = settings.VK_API_VERSION
        self.base_url = "https://api.vk.com/method/"
        self._session: aiohttp.ClientSession | None = None
        
        # Инициализация всех разделов
        self.account = AccountAPI(self._make_request)
        self.friends = FriendsAPI(self._make_request)
        self.groups = GroupsAPI(self._make_request)
        self.likes = LikesAPI(self._make_request)
        self.messages = MessagesAPI(self._make_request)
        self.newsfeed = NewsfeedAPI(self._make_request)
        self.photos = PhotosAPI(self._make_request, self) # Передаем self для доступа к сессии
        self.stories = StoriesAPI(self._make_request)
        self.users = UsersAPI(self._make_request)
        self.wall = WallAPI(self._make_request)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Ленивая инициализация сессии aiohttp."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Закрывает сессию. Важно вызывать при завершении работы с объектом."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if params is None: params = {}
        
        params['access_token'] = self.access_token
        params['v'] = self.api_version

        session = await self._get_session()
        try:
            for attempt in range(3): # Логика повторных попыток сохранена
                async with session.post(f"{self.base_url}{method}", data=params, proxy=self.proxy) as response:
                    # Проверяем, что ответ действительно JSON, чтобы избежать ошибок
                    if response.content_type != 'application/json':
                         raw_text = await response.text()
                         raise VKAPIError(f"VK API вернул не-JSON ответ. Статус: {response.status}. Ответ: {raw_text[:200]}", 0)

                    data = await response.json()
                    
                    if 'error' in data:
                        error_data = data['error']
                        error_code = error_data.get('error_code')
                        error_msg = error_data.get('error_msg', 'Unknown VK error')
                        
                        if error_code in [6, 9]: # Rate Limit или Flood Control
                            wait_time = 1.5 + attempt * 2
                            await asyncio.sleep(wait_time)
                            continue

                        ExceptionClass = ERROR_CODE_MAP.get(error_code, VKAPIError)
                        raise ExceptionClass(error_msg, error_code)

                    return data.get('response')
            
            # Если все попытки исчерпаны
            raise VKFloodControlError("Превышено количество попыток после ошибок Flood/Rate Control.", 9)

        except aiohttp.ClientError as e:
            # Более детальное сообщение об ошибке
            raise VKAPIError(f"Сетевая ошибка ({type(e).__name__}): {e}. Проверьте прокси и подключение к интернету.", 0)

    async def execute(self, calls: List[Dict[str, Any]]) -> Optional[List[Any]]:
        if not 25 >= len(calls) > 0:
            raise ValueError("Количество вызовов для метода execute должно быть от 1 до 25.")
        # Использование f-строк и json.dumps для большей безопасности и читаемости
        code_lines = [f'API.{call["method"]}({json.dumps(call.get("params", {}), ensure_ascii=False)})' for call in calls]
        code = f"return [{','.join(code_lines)}];"
        return await self._make_request("execute", params={"code": code})


async def is_token_valid(vk_token: str) -> Optional[int]:
    """Вспомогательная функция для проверки токена при логине."""
    vk_api = VKAPI(access_token=vk_token)
    try:
        user_info = await vk_api.users.get()
        return user_info.get('id') if user_info else None
    except VKAPIError:
        return None
    finally:
        # Важно закрыть сессию после использования
        await vk_api.close()
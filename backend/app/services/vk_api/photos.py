# --- backend/app/services/vk_api/photos.py ---

from typing import Optional, Dict, Any
from .base import BaseVKSection
import aiohttp

# Импортируем VKAPI для type hinting и избежания циклического импорта
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from . import VKAPI

class PhotosAPI(BaseVKSection):
    # УЛУЧШЕНИЕ: Принимаем родительский объект VKAPI для доступа к общей сессии
    def __init__(self, request_method: callable, vk_api_client: 'VKAPI'):
        super().__init__(request_method)
        self._vk_api_client = vk_api_client

    async def getAll(self, owner_id: int, count: int = 200) -> Optional[Dict[str, Any]]:
        params = {"owner_id": owner_id, "count": count, "extended": 1}
        return await self._make_request("photos.getAll", params=params)

    async def getWallUploadServer(self) -> Optional[Dict[str, Any]]:
        return await self._make_request('photos.getWallUploadServer')

    async def saveWallPhoto(self, upload_data: dict) -> Optional[Dict[str, Any]]:
        return await self._make_request('photos.saveWallPhoto', params=upload_data)
        
    async def upload_for_wall(self, photo_data: bytes) -> Optional[str]:
        upload_server = await self.getWallUploadServer()
        if not upload_server or 'upload_url' not in upload_server:
            return None
        
        form = aiohttp.FormData()
        form.add_field('photo', photo_data, filename='photo.jpg', content_type='image/jpeg')
        
        # УЛУЧШЕНИЕ: Используем общую сессию из родительского VKAPI клиента
        session = await self._vk_api_client._get_session()
        # Таймаут для загрузки файла может быть больше, поэтому устанавливаем его явно
        timeout = aiohttp.ClientTimeout(total=45)
        async with session.post(upload_server['upload_url'], data=form, proxy=self._vk_api_client.proxy, timeout=timeout) as resp:
            # Добавлена проверка статуса ответа
            resp.raise_for_status()
            upload_result = await resp.json()

        # Проверяем, что в ответе есть необходимые поля
        if not all(k in upload_result for k in ['server', 'photo', 'hash']):
             return None

        saved_photo_list = await self.saveWallPhoto(upload_data=upload_result)
        if not saved_photo_list or not saved_photo_list[0]:
            return None
        
        photo = saved_photo_list[0]
        return f"photo{photo['owner_id']}_{photo['id']}"
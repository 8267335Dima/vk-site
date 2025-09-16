# --- backend/app/services/vk_api/photos.py ---

import json # <--- ДОБАВЛЕН ИМПОРТ
from typing import Optional, Dict, Any
from .base import BaseVKSection
import aiohttp

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from . import VKAPI

class PhotosAPI(BaseVKSection):
    def __init__(self, request_method: callable, vk_api_client: 'VKAPI'):
        super().__init__(request_method)
        self._vk_api_client = vk_api_client

    async def getAll(self, owner_id: int, count: int = 200) -> Optional[Dict[str, Any]]:
        params = {"owner_id": owner_id, "count": count, "extended": 1}
        return await self._make_request("photos.getAll", params=params)

    async def getWallUploadServer(self) -> Optional[Dict[str, Any]]:
        return await self._make_request('photos.getWallUploadServer')

    async def saveWallPhoto(self, upload_data: dict) -> Optional[Dict[str, Any]]:
        if 'photo' in upload_data and not isinstance(upload_data['photo'], str):
            upload_data['photo'] = json.dumps(upload_data['photo'], ensure_ascii=False)
        return await self._make_request('photos.saveWallPhoto', params=upload_data)
        
    async def upload_for_wall(self, photo_data: bytes) -> Optional[str]:
        upload_server = await self.getWallUploadServer()
        if not upload_server or 'upload_url' not in upload_server:
            return None
        
        form = aiohttp.FormData()
        form.add_field('photo', photo_data, filename='photo.jpg', content_type='image/jpeg')
        
        session = await self._vk_api_client._get_session()
        timeout = aiohttp.ClientTimeout(total=45)
        
        # Оборачиваем в try-except для лучшего логгирования ошибки
        try:
            async with session.post(upload_server['upload_url'], data=form, proxy=self._vk_api_client.proxy, timeout=timeout) as resp:
                resp.raise_for_status()
                # VK может вернуть text/plain, поэтому явно указываем content_type=None
                upload_result = await resp.json(content_type=None)
        except Exception as e:
            # Если ошибка на этом этапе, мы будем знать точно, где она
            print(f"ОШИБКА при загрузке на сервер VK: {e}")
            raise

        if not all(k in upload_result for k in ['server', 'photo', 'hash']):
             return None

        saved_photo_list = await self.saveWallPhoto(upload_data=upload_result)
        if not saved_photo_list or not saved_photo_list[0]:
            return None
        
        photo = saved_photo_list[0]
        return f"photo{photo['owner_id']}_{photo['id']}"
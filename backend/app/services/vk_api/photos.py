from typing import Optional, Dict, Any
from .base import BaseVKSection
import aiohttp

class PhotosAPI(BaseVKSection):
    async def getAll(self, owner_id: int, count: int = 200) -> Optional[Dict[str, Any]]:
        params = {"owner_id": owner_id, "count": count, "extended": 1}
        return await self._make_request("photos.getAll", params=params)

    async def getWallUploadServer(self) -> Optional[Dict[str, Any]]:
        return await self._make_request('photos.getWallUploadServer')

    async def saveWallPhoto(self, upload_data: dict) -> Optional[Dict[str, Any]]:
        return await self._make_request('photos.saveWallPhoto', params=upload_data)
        
    async def upload_for_wall(self, photo_data: bytes, proxy: Optional[str] = None) -> Optional[str]:
        upload_server = await self.getWallUploadServer()
        if not upload_server or 'upload_url' not in upload_server:
            return None
        
        form = aiohttp.FormData()
        form.add_field('photo', photo_data, filename='photo.jpg', content_type='image/jpeg')
        
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_server['upload_url'], data=form, proxy=proxy, timeout=30) as resp:
                upload_result = await resp.json()

        saved_photo = await self.saveWallPhoto(upload_data=upload_result)
        if not saved_photo or not saved_photo[0]:
            return None
        
        photo = saved_photo[0]
        return f"photo{photo['owner_id']}_{photo['id']}"
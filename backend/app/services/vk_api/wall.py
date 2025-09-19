# backend/app/services/vk_api/wall.py

from typing import Optional, Dict, Any
from .base import BaseVKSection

class WallAPI(BaseVKSection):
    async def get(self, owner_id: int, count: int = 5) -> Optional[Dict[str, Any]]:
        return await self._make_request("wall.get", params={"owner_id": owner_id, "count": count})

    async def post(self, owner_id: int, message: str, attachments: str, from_group: bool = False) -> Optional[Dict[str, Any]]:
        """Публикует пост на стене. Может публиковать от имени группы."""
        params = {
            "owner_id": owner_id,
            "message": message,
            "attachments": attachments
        }
        if from_group:
            params["from_group"] = 1
            
        return await self._make_request("wall.post", params=params)

    async def delete(self, post_id: int, owner_id: Optional[int] = None) -> Optional[int]:
        params = {"post_id": post_id}
        if owner_id:
            params["owner_id"] = owner_id
        return await self._make_request("wall.delete", params=params)
    
    async def getComments(self, owner_id: int, post_id: int, count: int = 100) -> Optional[Dict[str, Any]]:
        params = {"owner_id": owner_id, "post_id": post_id, "count": count, "thread_items_count": 0}
        return await self._make_request("wall.getComments", params=params)
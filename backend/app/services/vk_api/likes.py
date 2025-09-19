from typing import Optional, Dict, Any
from .base import BaseVKSection

class LikesAPI(BaseVKSection):
    async def add(self, item_type: str, owner_id: int, item_id: int) -> Optional[Dict[str, Any]]:
        params = {"type": item_type, "owner_id": owner_id, "item_id": item_id}
        return await self._make_request("likes.add", params=params)
    
    async def getList(self, type: str, owner_id: int, item_id: int, count: int = 1000) -> Optional[Dict[str, Any]]:
        params = {"type": type, "owner_id": owner_id, "item_id": item_id, "filter": "likes", "count": count}
        return await self._make_request("likes.getList", params=params)
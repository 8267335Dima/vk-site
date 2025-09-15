from typing import Optional, Dict, Any
from .base import BaseVKSection

class LikesAPI(BaseVKSection):
    async def add(self, item_type: str, owner_id: int, item_id: int) -> Optional[Dict[str, Any]]:
        params = {"type": item_type, "owner_id": owner_id, "item_id": item_id}
        return await self._make_request("likes.add", params=params)
from typing import Optional, Dict, Any
from .base import BaseVKSection

class WallAPI(BaseVKSection):
    async def get(self, owner_id: int, count: int = 5) -> Optional[Dict[str, Any]]:
        return await self._make_request("wall.get", params={"owner_id": owner_id, "count": count})

    async def post(self, owner_id: int, message: str, attachments: str) -> Optional[Dict[str, Any]]:
        params = {"owner_id": owner_id, "from_group": 0, "message": message, "attachments": attachments}
        return await self._make_request("wall.post", params=params)
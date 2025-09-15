from typing import Optional, Dict, Any
from .base import BaseVKSection

class StoriesAPI(BaseVKSection):
    async def get(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("stories.get", params={})
from typing import Optional, Dict, Any
from .base import BaseVKSection

class NewsfeedAPI(BaseVKSection):
    async def get(self, count: int, filters: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает список новостей для текущего пользователя.
        https://dev.vk.com/method/newsfeed.get
        """
        params = {"count": count, "filters": filters}
        return await self._make_request("newsfeed.get", params=params)
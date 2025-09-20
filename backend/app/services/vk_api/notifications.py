from typing import Optional, Dict, Any, List
from .base import BaseVKSection

class NotificationsAPI(BaseVKSection):
    async def get(self, count: int = 30, start_time: Optional[int] = None, filters: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        params = {"count": count}
        if start_time:
            params["start_time"] = start_time
        if filters:
            params["filters"] = ",".join(filters)
        return await self._make_request("notifications.get", params=params)

    async def markAsViewed(self) -> Optional[int]:
        return await self._make_request("notifications.markAsViewed")
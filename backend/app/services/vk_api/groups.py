from typing import Optional, Dict, Any
from .base import BaseVKSection

class GroupsAPI(BaseVKSection):
    async def get(self, user_id: int, extended: int = 1, fields: str = "members_count", count: int = 1000) -> Optional[Dict[str, Any]]:
        params = {"user_id": user_id, "extended": extended, "fields": fields, "count": count}
        return await self._make_request("groups.get", params=params)

    async def leave(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.leave", params={"group_id": group_id})

    async def search(self, query: str, count: int = 100, sort: int = 6) -> Optional[Dict[str, Any]]:
        return await self._make_request("groups.search", params={"q": query, "count": count, "sort": sort})

    async def join(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.join", params={"group_id": group_id})
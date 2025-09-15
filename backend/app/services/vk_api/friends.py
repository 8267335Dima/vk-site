
#backend/app/services/vk_api/friends.py

from typing import Optional, Dict, Any
from .base import BaseVKSection

class FriendsAPI(BaseVKSection):
    async def get(self, user_id: int, fields: str, order: str = "random") -> Optional[Dict[str, Any]]:
        params = {"user_id": user_id, "fields": fields, "order": order}
        response = await self._make_request("friends.get", params=params)
        if not response or "items" not in response:
            return None
        # Возвращаем полный ответ, т.к. он содержит `count`
        return response

    async def getRequests(self, count: int = 1000, extended: int = 0, **kwargs) -> Optional[Dict[str, Any]]:
        params = {"count": count, "extended": extended, **kwargs}
        if extended == 1:
            params['fields'] = "sex,online,last_seen,is_closed,status,counters"
        return await self._make_request("friends.getRequests", params=params)

    async def getSuggestions(self, count: int = 200, fields: str = "sex,online,last_seen,is_closed,status,counters,photo_id") -> Optional[Dict[str, Any]]:
        params = {"filter": "mutual", "count": count, "fields": fields}
        return await self._make_request("friends.getSuggestions", params)

    async def add(self, user_id: int, text: Optional[str] = None) -> Optional[int]:
        params = {"user_id": user_id}
        if text: params["text"] = text
        return await self._make_request("friends.add", params=params)

    async def delete(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self._make_request("friends.delete", params={"user_id": user_id})
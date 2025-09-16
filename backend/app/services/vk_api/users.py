# backend/app/services/vk_api/users.py

from typing import Optional, Any
from .base import BaseVKSection

class UsersAPI(BaseVKSection):
    async def get(self, user_ids: Optional[str] = None, fields: Optional[str] = "photo_200,sex,online,last_seen,is_closed,status,counters,photo_id") -> Optional[Any]:
        params = {'fields': fields}
        if user_ids:
            params['user_ids'] = user_ids
        response = await self._make_request("users.get", params=params)
        
        if response and isinstance(response, list):
            return response

            
        return None
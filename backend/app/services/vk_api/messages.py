import random
from typing import Optional, Dict, Any, Literal
from .base import BaseVKSection

class MessagesAPI(BaseVKSection):
    async def send(self, user_id: int, message: str) -> Optional[int]:
        params = {"user_id": user_id, "message": message, "random_id": random.randint(0, 2**31)}
        return await self._make_request("messages.send", params=params)
    
    async def getConversations(self, count: int = 200, filter: Optional[Literal['all', 'unread', 'important', 'unanswered']] = 'all') -> Optional[Dict[str, Any]]:
        params = {"count": count, "filter": filter}
        return await self._make_request("messages.getConversations", params=params)
import random
from typing import Optional, Dict, Any, Literal
from .base import BaseVKSection

class MessagesAPI(BaseVKSection):
    async def send(self, user_id: int, message: str, attachment: Optional[str] = None) -> Optional[int]:
        params = {
            "user_id": user_id,
            "message": message,
            "random_id": random.randint(0, 2**31)
        }
        # --- ДОБАВЛЕНО ---
        if attachment:
            params["attachment"] = attachment
        # -----------------
        return await self._make_request("messages.send", params=params)

    async def getConversations(self, count: int = 200, filter: Optional[Literal['all', 'unread', 'important', 'unanswered']] = 'all') -> Optional[Dict[str, Any]]:
        params = {"count": count, "filter": filter}
        return await self._make_request("messages.getConversations", params=params)
    
    async def markAsRead(self, peer_id: int) -> Optional[int]:
        """Отмечает сообщения как прочитанные."""
        params = {"peer_id": peer_id}
        return await self._make_request("messages.markAsRead", params=params)

    # НОВЫЙ МЕТОД:
    async def setActivity(self, user_id: int, type: str = 'typing') -> Optional[int]:
        """Показывает статус 'набирает сообщение'."""
        params = {"user_id": user_id, "type": type}
        return await self._make_request("messages.setActivity", params=params)
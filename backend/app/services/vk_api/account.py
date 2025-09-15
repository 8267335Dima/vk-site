#backend/app/services/vk_api/account.py

from typing import Optional
from .base import BaseVKSection

class AccountAPI(BaseVKSection):
    async def setOnline(self) -> Optional[int]:
        return await self._make_request("account.setOnline")
from .base import BaseVKSection

class BoardAPI(BaseVKSection):
    async def getComments(self, **kwargs):
        return await self._make_request("board.getComments", params=kwargs)
# --- backend/app/services/vk_api.py ---
import aiohttp
import random
import json
from typing import Optional, Dict, Any, List
from app.core.config import settings

class VKAPIError(Exception):
    def __init__(self, message: str, error_code: int):
        self.message = message
        self.error_code = error_code
        super().__init__(f"VK API Error [{self.error_code}]: {self.message}")

class VKRateLimitError(VKAPIError): pass
class VKInvalidTokenError(VKAPIError): pass
class VKAccessDeniedError(VKAPIError): pass
class VKAuthError(VKAPIError): pass

class VKAPI:
    def __init__(self, access_token: str, proxy: Optional[str] = None):
        self.access_token = access_token
        self.proxy = proxy
        self.api_version = settings.VK_API_VERSION
        self.base_url = "https://api.vk.com/method/"

    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if params is None:
            params = {}
        
        params['access_token'] = self.access_token
        params['v'] = self.api_version

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}{method}", data=params, proxy=self.proxy, timeout=20) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if 'error' in data:
                        error_data = data['error']
                        error_code = error_data.get('error_code')
                        error_msg = error_data.get('error_msg', 'Unknown VK error')
                        
                        if error_code == 5: raise VKAuthError(error_msg, error_code)
                        elif error_code == 6: raise VKRateLimitError(error_msg, error_code)
                        elif error_code in [15, 18, 203, 902]: raise VKAccessDeniedError(error_msg, error_code)
                        else: raise VKAPIError(error_msg, error_code)

                    return data.get('response')
            except aiohttp.ClientError as e:
                raise VKAPIError(f"HTTP Request failed: {e}", 0)

    async def execute(self, calls: List[Dict[str, Any]]) -> Optional[List[Any]]:
        if not 25 >= len(calls) > 0:
            raise ValueError("Number of calls for execute method must be between 1 and 25.")

        code_lines = [f'API.{call["method"]}({json.dumps(call.get("params", {}), ensure_ascii=False)})' for call in calls]
        code = f"return [{','.join(code_lines)}];"
        
        return await self._make_request("execute", params={"code": code})

    async def get_user_info(self, user_ids: Optional[str] = None, fields: Optional[str] = "photo_200,sex,online,last_seen,is_closed,status,counters,photo_id") -> Optional[Any]:
        params = {'fields': fields}
        if user_ids:
            params['user_ids'] = user_ids
        response = await self._make_request("users.get", params=params)
        return response

    async def get_user_friends(self, user_id: int, fields: str = "sex,bdate,city,online,last_seen,is_closed,deactivated") -> Optional[List[Dict[str, Any]]]:
        params = {"user_id": user_id, "fields": fields, "order": "random"}
        response = await self._make_request("friends.get", params=params)
        return response.get("items") if response else None

    async def add_friend(self, user_id: int, text: Optional[str] = None) -> Optional[Dict[str, Any]]:
        params = {"user_id": user_id}
        if text:
            params["text"] = text
        return await self._make_request("friends.add", params=params)

    async def get_wall(self, owner_id: int, count: int = 5) -> Optional[Dict[str, Any]]:
        return await self._make_request("wall.get", params={"owner_id": owner_id, "count": count})

    # УЛУЧШЕНИЕ: Добавлен метод для постинга на стену
    async def wall_post(self, owner_id: Optional[int] = None, message: Optional[str] = None, attachments: Optional[str] = None) -> Optional[Dict[str, Any]]:
        params = {}
        if owner_id:
            params['owner_id'] = owner_id
        if message:
            params['message'] = message
        if attachments:
            params['attachments'] = attachments
        return await self._make_request("wall.post", params=params)

    # ИСПРАВЛЕНИЕ: Добавлен недостающий метод для удаления поста
    async def wall_delete(self, owner_id: Optional[int] = None, post_id: int = None) -> Optional[int]:
        params = {'post_id': post_id}
        if owner_id:
            params['owner_id'] = owner_id
        return await self._make_request("wall.delete", params=params)
        
    async def get_stories(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("stories.get", params={})

    async def get_incoming_friend_requests(self, count: int = 1000, **kwargs) -> Optional[Dict[str, Any]]:
        params = {"count": count, **kwargs}
        if 'extended' in params and params['extended'] == 1:
            params['fields'] = "sex,online,last_seen,is_closed,status,counters"
        return await self._make_request("friends.getRequests", params=params)

    async def add_like(self, item_type: str, owner_id: int, item_id: int) -> Optional[Dict[str, Any]]:
        return await self._make_request("likes.add", params={"type": item_type, "owner_id": owner_id, "item_id": item_id})
    
    async def delete_friend(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self._make_request("friends.delete", params={"user_id": user_id})

    async def send_message(self, user_id: int, message: str) -> Optional[int]:
        return await self._make_request("messages.send", params={"user_id": user_id, "message": message, "random_id": random.randint(0, 2**31)})

    async def get_conversations(self, count: int = 200) -> Optional[Dict[str, Any]]:
        return await self._make_request("messages.getConversations", params={"count": count})

    async def get_photos(self, owner_id: int, count: int = 200, extended: int = 1) -> Optional[Dict[str, Any]]:
        return await self._make_request("photos.getAll", params={"owner_id": owner_id, "count": count, "extended": extended})

    async def set_online(self) -> Optional[int]:
        return await self._make_request("account.setOnline")
    
    async def get_groups(self, user_id: int, extended: int = 1, fields: str = "members_count", count: int = 1000) -> Optional[Dict[str, Any]]:
        return await self._make_request("groups.get", params={"user_id": user_id, "extended": extended, "fields": fields, "count": count})

    async def leave_group(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.leave", params={"group_id": group_id})

    async def search_groups(self, query: str, count: int = 100, sort: int = 6) -> Optional[Dict[str, Any]]:
        return await self._make_request("groups.search", params={"q": query, "count": count, "sort": sort})
    
    async def join_group(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.join", params={"group_id": group_id})

async def is_token_valid(vk_token: str) -> Optional[int]:
    vk_api = VKAPI(access_token=vk_token)
    try:
        user_info = await vk_api.get_user_info()
        return user_info[0].get('id') if isinstance(user_info, list) and user_info else None
    except VKAPIError:
        return None
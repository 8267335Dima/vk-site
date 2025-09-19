# backend/app/services/group_identity_service.py
from typing import Dict, Any
from app.services.vk_api import VKAPI, VKAPIError
import structlog

log = structlog.get_logger(__name__)

class GroupIdentityService:
    @staticmethod
    async def get_group_info_by_token(group_token: str, group_id: int) -> Dict[str, Any] | None:
        """Проверяет токен группы и возвращает информацию о ней."""
        vk_api = VKAPI(access_token=group_token)
        try:
            # Выполняем запрос от имени группы, чтобы проверить токен
            response = await vk_api.groups.getById(group_id=str(group_id), fields="photo_100")
            if not response or not isinstance(response, list) or len(response) == 0:
                return None
            
            group_info = response[0]
            
            # Дополнительная проверка, что токен принадлежит именно этой группе
            if group_info.get("id") != group_id:
                log.warn("group_token.mismatch", expected_id=group_id, actual_id=group_info.get("id"))
                return None
            
            return {
                "vk_group_id": group_info["id"],
                "name": group_info["name"],
                "photo_100": group_info.get("photo_100")
            }
        except VKAPIError as e:
            log.error("group_token.validation_failed", error=str(e))
            return None
        finally:
            await vk_api.close()
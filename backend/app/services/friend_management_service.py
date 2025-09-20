from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import RemoveFriendsRequest
from .interfaces import IExecutableTask, IPreviewableTask

class FriendManagementService(BaseVKService, IExecutableTask, IPreviewableTask):
    async def get_targets(self, params: RemoveFriendsRequest) -> List[Dict[str, Any]]:
        await self._initialize_vk_api()
        response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,is_closed,deactivated")
        if not response or not response.get('items'):
            return []
        all_friends = response.get('items', [])
        banned_friends = [f for f in all_friends if f.get('deactivated') in ['banned', 'deleted']] if params.filters.remove_banned else []
        active_friends = [f for f in all_friends if not f.get('deactivated')]
        filtered_active_friends = await apply_filters_to_profiles(active_friends, params.filters)
        return banned_friends + filtered_active_friends

    async def execute(self, params: RemoveFriendsRequest) -> str:
        await self._initialize_vk_api()
        stats = await self._get_today_stats()
        targets = await self.get_targets(params)
        if not targets:
            return "Друзей для удаления по заданным критериям не найдено."
        targets_to_process = targets[:params.count]
        processed_count = 0
        batch_size = 25
        for i in range(0, len(targets_to_process), batch_size):
            batch = targets_to_process[i:i + batch_size]
            calls = [{"method": "friends.delete", "params": {"user_id": friend.get('id')}} for friend in batch]
            await self.humanizer.think(action_type='like')
            results = await self.vk_api.execute(calls)
            if results is None:
                await self.emitter.send_log(f"Пакетный запрос на удаление не удался.", "error")
                continue
            for friend, result in zip(batch, results):
                user_id = friend.get('id')
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"
                if isinstance(result, dict) and result.get('success') == 1:
                    processed_count += 1
                    await self._increment_stat(stats, 'friends_removed_count')
                    reason = f"({friend.get('deactivated', 'неактивность')})"
                    await self.emitter.send_log(f"Удален друг: {name} {reason}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', 'неизвестная ошибка') if isinstance(result, dict) else 'неизвестная ошибка'
                    await self.emitter.send_log(f"Не удалось удалить друга {name}. Причина: {error_msg}", "error", target_url=url)
        return f"Чистка завершена. Удалено друзей: {processed_count}."
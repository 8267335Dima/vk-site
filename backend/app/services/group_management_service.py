from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.api.schemas.actions import LeaveGroupsRequest, JoinGroupsRequest
from .interfaces import IExecutableTask, IPreviewableTask

class GroupManagementService(BaseVKService, IExecutableTask, IPreviewableTask):
    async def get_targets(self, params: LeaveGroupsRequest | JoinGroupsRequest) -> List[Dict[str, Any]]:
        await self._initialize_vk_api()
        if isinstance(params, LeaveGroupsRequest):
            response = await self.vk_api.groups.get(user_id=self.user.vk_id, extended=1)
            if not response or not response.get('items'): return []
            all_groups = [g for g in response['items'] if g.get('type') != 'event']
            keyword = (params.filters.status_keyword or "").lower().strip()
            if not keyword: return all_groups
            return [g for g in all_groups if keyword in g.get('name', '').lower()]
        elif isinstance(params, JoinGroupsRequest):
            keyword = (params.filters.status_keyword or "").strip()
            if not keyword: return []
            search_response = await self.vk_api.groups.search(query=keyword, count=params.count * 2)
            if not search_response or not search_response.get('items'): return []
            user_groups_response = await self.vk_api.groups.get(user_id=self.user.vk_id, extended=0)
            user_group_ids = set(user_groups_response.get('items', [])) if user_groups_response else set()
            return [g for g in search_response['items'] if g['id'] not in user_group_ids and g.get('is_closed', 1) == 0]
        return []

    async def execute(self, params: LeaveGroupsRequest | JoinGroupsRequest) -> str:
        await self._initialize_vk_api()
        stats = await self._get_today_stats()
        targets = await self.get_targets(params)
        if not targets:
            return "Подходящих сообществ не найдено."
        targets_to_process = targets[:params.count]
        processed_count = 0
        if isinstance(params, LeaveGroupsRequest):
            for group in targets_to_process:
                if stats.groups_left_count >= self.user.daily_leave_groups_limit: break
                if await self.vk_api.groups.leave(group['id']) == 1:
                    processed_count += 1
                    await self._increment_stat(stats, 'groups_left_count')
            return f"Завершено. Покинуто сообществ: {processed_count}."
        elif isinstance(params, JoinGroupsRequest):
            for group in targets_to_process:
                if stats.groups_joined_count >= self.user.daily_join_groups_limit: break
                if await self.vk_api.groups.join(group['id']) == 1:
                    processed_count += 1
                    await self._increment_stat(stats, 'groups_joined_count')
            return f"Завершено. Вступлений в сообщества: {processed_count}."
        return "Неизвестный тип задачи."
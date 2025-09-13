# --- backend/app/services/group_management_service.py ---
from typing import Dict, Any
import asyncio
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError

class GroupManagementService(BaseVKService):

    async def leave_groups_by_criteria(self, **kwargs):
        settings: Dict[str, Any] = kwargs
        return await self._execute_logic(self._leave_groups_logic, settings)

    async def _leave_groups_logic(self, settings: Dict[str, Any]):
        count = settings.get('count', 50)
        filters = settings.get('filters', {})
        
        await self.emitter.send_log(f"Запуск задачи: отписаться от {count} сообществ.", "info")

        response = await self.vk_api.get_groups(user_id=self.user.vk_id)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не удалось получить список сообществ или вы не состоите в группах.", "warning")
            return
        
        all_groups = [g for g in response['items'] if g.get('type') != 'event']
        
        groups_to_leave = all_groups
        keyword = filters.get('status_keyword', '').lower().strip()

        if keyword:
            groups_to_leave = [
                group for group in all_groups if keyword in group.get('name', '').lower()
            ]
            await self.emitter.send_log(f"Найдено {len(groups_to_leave)} сообществ по ключевому слову '{keyword}'.", "info")
        
        if not groups_to_leave:
            await self.emitter.send_log("Сообществ для отписки по заданным критериям не найдено.", "success")
            return

        groups_to_leave = groups_to_leave[:count]
        
        processed_count = 0
        for group in groups_to_leave:
            group_id = group['id']
            group_name = group['name']
            url = f"https://vk.com/public{group_id}"
            
            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.leave_group(group_id)

            if result == 1:
                processed_count += 1
                await self.emitter.send_log(f"Вы успешно покинули сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось покинуть сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Покинуто сообществ: {processed_count}.", "success")

    async def join_groups_by_criteria(self, **kwargs):
        settings: Dict[str, Any] = kwargs
        return await self._execute_logic(self._join_groups_logic, settings)

    async def _join_groups_logic(self, settings: Dict[str, Any]):
        count = settings.get('count', 20)
        filters = settings.get('filters', {})
        keyword = filters.get('status_keyword', '').strip()

        if not keyword:
            await self.emitter.send_log("Не указано ключевое слово для поиска групп.", "error")
            return

        await self.emitter.send_log(f"Запуск задачи: вступить в {count} сообществ по запросу '{keyword}'.", "info")

        response = await self.vk_api.search_groups(query=keyword, count=count * 2)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не найдено сообществ по вашему запросу.", "warning")
            return

        user_groups_response = await self.vk_api.get_groups(user_id=self.user.vk_id)
        user_group_ids = set(user_groups_response.get('items', []) if user_groups_response else [])

        groups_to_join = [
            g for g in response['items'] 
            if g['id'] not in user_group_ids and g.get('is_closed', 1) == 0
        ][:count]

        if not groups_to_join:
            await self.emitter.send_log("Новых открытых сообществ для вступления не найдено.", "success")
            return
        
        processed_count = 0
        for group in groups_to_join:
            group_id = group['id']
            group_name = group['name']
            url = f"https://vk.com/public{group_id}"

            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.join_group(group_id)

            if result == 1:
                processed_count += 1
                await self.emitter.send_log(f"Успешное вступление в сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось вступить в сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Вступлений в сообщества: {processed_count}.", "success")
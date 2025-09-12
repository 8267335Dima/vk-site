# backend/app/services/group_management_service.py
from typing import Dict, Any
import asyncio
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError

class GroupManagementService(BaseVKService):

    async def leave_groups_by_criteria(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._leave_groups_logic, count, filters)

    async def _leave_groups_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Запуск задачи: отписаться от {count} сообществ.", "info")
        stats = await self._get_today_stats()

        response = await self.vk_api.get_groups(user_id=self.user.vk_id)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не удалось получить список сообществ.", "warning")
            return
        
        all_groups = response['items']
        
        groups_to_leave = []
        keyword = filters.get('status_keyword', '').lower().strip()

        if keyword:
            groups_to_leave = [
                group for group in all_groups if keyword in group.get('name', '').lower()
            ]
            await self.emitter.send_log(f"Найдено {len(groups_to_leave)} сообществ по ключевому слову '{keyword}'.", "info")
        else:
            groups_to_leave = all_groups # Если нет ключевого слова, отписываемся от всех подряд
        
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
                # Можно добавить новую колонку в DailyStats для отписок, если нужно
                await self.emitter.send_log(f"Вы успешно покинули сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось покинуть сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Покинуто сообществ: {processed_count}.", "success")
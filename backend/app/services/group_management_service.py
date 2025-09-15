# --- backend/app/services/group_management_service.py ---
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.api.schemas.actions import LeaveGroupsRequest, JoinGroupsRequest

class GroupManagementService(BaseVKService):

    # --- НОВЫЙ МЕТОД ДЛЯ ПОИСКА ЦЕЛЕЙ НА ВЫХОД ---
    async def get_leave_groups_targets(self, params: LeaveGroupsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает список сообществ пользователя и фильтрует их по ключевому слову.
        """
        response = await self.vk_api.get_groups(user_id=self.user.vk_id)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не удалось получить список сообществ или вы не состоите в группах.", "warning")
            return []
        
        # Исключаем мероприятия из списка
        all_groups = [g for g in response['items'] if g.get('type') != 'event']
        
        keyword = (params.filters.status_keyword or "").lower().strip()
        if not keyword:
            # Если нет ключевого слова, возвращаем все группы (задача сама ограничит количество)
            return all_groups

        groups_to_leave = [group for group in all_groups if keyword in group.get('name', '').lower()]
        await self.emitter.send_log(f"Найдено {len(groups_to_leave)} сообществ по ключевому слову '{keyword}'.", "info")
        
        return groups_to_leave

    async def leave_groups_by_criteria(self, params: LeaveGroupsRequest):
        return await self._execute_logic(self._leave_groups_logic, params)

    async def _leave_groups_logic(self, params: LeaveGroupsRequest):
        await self.emitter.send_log(f"Запуск задачи: отписаться от {params.count} сообществ.", "info")

        targets = await self.get_leave_groups_targets(params)
        
        if not targets:
            await self.emitter.send_log("Сообществ для отписки по заданным критериям не найдено.", "success")
            return

        targets_to_process = targets[:params.count]
        
        processed_count = 0
        for group in targets_to_process:
            group_id, group_name = group['id'], group['name']
            url = f"https://vk.com/public{group_id}"
            
            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.leave_group(group_id)

            if result == 1:
                processed_count += 1
                await self.emitter.send_log(f"Вы успешно покинули сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось покинуть сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Покинуто сообществ: {processed_count}.", "success")

    # --- НОВЫЙ МЕТОД ДЛЯ ПОИСКА ЦЕЛЕЙ НА ВСТУПЛЕНИЕ ---
    async def get_join_groups_targets(self, params: JoinGroupsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Ищет сообщества по ключевому слову и отфильтровывает те,
        в которых пользователь уже состоит или которые являются закрытыми.
        """
        keyword = (params.filters.status_keyword or "").strip()
        if not keyword:
            await self.emitter.send_log("Не указано ключевое слово для поиска групп.", "error")
            return []

        search_response = await self.vk_api.search_groups(query=keyword, count=params.count * 2)
        if not search_response or not search_response.get('items'):
            await self.emitter.send_log("Не найдено сообществ по вашему запросу.", "warning")
            return []

        user_groups_response = await self.vk_api.get_groups(user_id=self.user.vk_id, extended=0)
        user_group_ids = set(user_groups_response.get('items', []) if user_groups_response else [])

        groups_to_join = [
            g for g in search_response['items'] 
            if g['id'] not in user_group_ids and g.get('is_closed', 1) == 0
        ]
        
        return groups_to_join

    async def join_groups_by_criteria(self, params: JoinGroupsRequest):
        return await self._execute_logic(self._join_groups_logic, params)

    async def _join_groups_logic(self, params: JoinGroupsRequest):
        keyword = (params.filters.status_keyword or "").strip()
        await self.emitter.send_log(f"Запуск задачи: вступить в {params.count} сообществ по запросу '{keyword}'.", "info")

        targets = await self.get_join_groups_targets(params)

        if not targets:
            await self.emitter.send_log("Новых открытых сообществ для вступления не найдено.", "success")
            return
        
        targets_to_process = targets[:params.count]
        
        processed_count = 0
        for group in targets_to_process:
            group_id, group_name = group['id'], group['name']
            url = f"https://vk.com/public{group_id}"

            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.join_group(group_id)

            if result == 1:
                processed_count += 1
                await self.emitter.send_log(f"Успешное вступление в сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось вступить в сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Вступлений в сообщества: {processed_count}.", "success")
# --- backend/app/services/friend_management_service.py ---
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import RemoveFriendsRequest

class FriendManagementService(BaseVKService):

    # --- НОВЫЙ МЕТОД ДЛЯ ПОИСКА ЦЕЛЕЙ ---
    async def get_remove_friends_targets(self, params: RemoveFriendsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает список друзей и фильтрует их по заданным критериям
        (забаненные, неактивные и т.д.).
        """
        await self.emitter.send_log("Получение полного списка друзей для анализа...", "info")
        all_friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,is_closed,deactivated")
        if not all_friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return []

        # Сначала отбираем забаненных/удаленных, если включена опция
        banned_friends = []
        if params.filters.remove_banned:
            banned_friends = [f for f in all_friends if f.get('deactivated') in ['banned', 'deleted']]
        
        # Затем работаем с остальными, активными друзьями
        active_friends = [f for f in all_friends if not f.get('deactivated')]
        
        await self.emitter.send_log(f"Найдено забаненных/удаленных: {len(banned_friends)}. Анализ активных друзей...", "info")
        
        # Применяем к активным друзьям остальные фильтры (неактивность, пол и т.д.)
        filtered_active_friends = await apply_filters_to_profiles(active_friends, params.filters)
        
        # Объединяем два списка: сначала "собачки", потом отфильтрованные
        friends_to_remove = banned_friends + filtered_active_friends
        
        return friends_to_remove

    async def remove_friends_by_criteria(self, params: RemoveFriendsRequest):
        return await self._execute_logic(self._remove_friends_by_criteria_logic, params)

    async def _remove_friends_by_criteria_logic(self, params: RemoveFriendsRequest):
        await self.emitter.send_log(f"Начинаем чистку друзей. Цель: удалить до {params.count} чел.", "info")
        stats = await self._get_today_stats()

        # --- ИЗМЕНЕНИЕ: Используем новый метод для получения целей ---
        targets = await self.get_remove_friends_targets(params)
        
        if not targets:
            await self.emitter.send_log("Друзей для удаления по заданным критериям не найдено.", "success")
            return

        # Ограничиваем итоговый список количеством, указанным в задаче
        targets_to_process = targets[:params.count]

        await self.emitter.send_log(f"Всего к удалению: {len(targets_to_process)} чел. Начинаем процесс...", "info")
        processed_count = 0
        
        batch_size = 25
        for i in range(0, len(targets_to_process), batch_size):
            batch = targets_to_process[i:i + batch_size]
            
            calls = [{"method": "friends.delete", "params": {"user_id": friend.get('id')}} for friend in batch]
            
            await self.humanizer.imitate_simple_action()
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

        await self.emitter.send_log(f"Чистка завершена. Удалено друзей: {processed_count}.", "success")
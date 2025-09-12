# backend/app/services/friend_management_service.py
import asyncio
from typing import Dict, Any, List
from app.services.base import BaseVKService

class FriendManagementService(BaseVKService):

    async def remove_friends_by_criteria(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._remove_friends_by_criteria_logic, count, filters)

    async def _remove_friends_by_criteria_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Начинаем чистку друзей. Цель: удалить {count} чел.", "info")
        stats = await self._get_today_stats()

        all_friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,is_closed,deactivated")
        if not all_friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return

        banned_friends = [f for f in all_friends if f.get('deactivated') in ['banned', 'deleted']]
        active_friends = [f for f in all_friends if not f.get('deactivated')]
        
        if not filters.get('remove_banned', True):
            banned_friends = []
        
        await self.emitter.send_log(f"Найдено забаненных/удаленных друзей: {len(banned_friends)}.", "info")
        
        filtered_active_friends = self._apply_filters_to_profiles(active_friends, filters)
        await self.emitter.send_log(f"Найдено друзей по критериям неактивности/пола: {len(filtered_active_friends)}.", "info")
        
        friends_to_remove = (banned_friends + filtered_active_friends)[:count]
        if not friends_to_remove:
            await self.emitter.send_log("Друзей для удаления по заданным критериям не найдено.", "success")
            return

        await self.emitter.send_log(f"Всего к удалению: {len(friends_to_remove)} чел. Начинаем процесс...", "info")
        processed_count = 0
        
        batch_size = 25
        for i in range(0, len(friends_to_remove), batch_size):
            batch = friends_to_remove[i:i + batch_size]
            
            calls = [
                {"method": "friends.delete", "params": {"user_id": friend['id']}}
                for friend in batch
            ]
            
            await self.humanizer.imitate_simple_action()
            
            results = await self.vk_api.execute(calls)
            
            if results is None:
                await self.emitter.send_log(f"Пакетный запрос на удаление не удался.", "error")
                continue

            for friend, result in zip(batch, results):
                user_id = friend['id']
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"

                if result and result.get('success') == 1:
                    processed_count += 1
                    await self._increment_stat(stats, 'friends_removed_count')
                    reason = f"({friend.get('deactivated', 'неактивность')})"
                    await self.emitter.send_log(f"Удален друг: {name} {reason}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', 'неизвестная ошибка') if isinstance(result, dict) else 'неизвестная ошибка'
                    await self.emitter.send_log(f"Не удалось удалить друга {name}. Причина: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Чистка завершена. Удалено друзей: {processed_count}.", "success")

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()
        for profile in profiles:
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True): continue
            if filters.get('sex') and profile.get('sex') != filters['sex']: continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts == 0: continue
            
            last_seen_days = filters.get('last_seen_days')
            if last_seen_days and (now_ts - last_seen_ts) > (last_seen_days * 86400):
                filtered_profiles.append(profile)
                continue

        return filtered_profiles
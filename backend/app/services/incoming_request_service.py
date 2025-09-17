# --- backend/app/services/incoming_request_service.py ---
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AcceptFriendsRequest

class IncomingRequestService(BaseVKService):

    async def get_accept_friends_targets(self, params: AcceptFriendsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает и фильтрует входящие заявки в друзья.
        """
        response = await self.vk_api.get_incoming_friend_requests(extended=1)
        if not response or not response.get('items'):
            await self.emitter.send_log("Входящие заявки не найдены.", "info")
            return []
        
        profiles = response.get('items', [])
        await self.emitter.send_log(f"Найдено {len(profiles)} заявок. Начинаем фильтрацию...", "info")
        
        filtered_profiles = await apply_filters_to_profiles(profiles, params.filters)
        return filtered_profiles

    async def accept_friend_requests(self, params: AcceptFriendsRequest):
        return await self._execute_logic(self._accept_friend_requests_logic, params)

    async def _accept_friend_requests_logic(self, params: AcceptFriendsRequest):
        await self.emitter.send_log("Начинаем прием заявок в друзья...", "info")
        stats = await self._get_today_stats()
        
        # ШАГ 1: Получаем цели
        targets = await self.get_accept_friends_targets(params)

        await self.emitter.send_log(f"После фильтрации осталось: {len(targets)}.", "info")
        
        if not targets:
            await self.emitter.send_log("Подходящих заявок для приема не найдено.", "success")
            return
        
        processed_count = 0
        batch_size = 25
        for i in range(0, len(targets), batch_size):
            batch = targets[i:i + batch_size]
            calls = [{"method": "friends.add", "params": {"user_id": p.get('id')}} for p in batch]

            await self.humanizer.think(action_type='add_friend')
            results = await self.vk_api.execute(calls)

            if results is None:
                await self.emitter.send_log("Пакетный запрос на принятие заявок не удался.", "error")
                continue

            for profile, result in zip(batch, results):
                user_id = profile.get('id')
                name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"
                
                if result in [1, 2, 4]:
                    processed_count += 1
                    await self._increment_stat(stats, 'friend_requests_accepted_count')
                    await self.emitter.send_log(f"Принята заявка от {name}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', f'неизвестная ошибка, код {result}') if isinstance(result, dict) else f'код {result}'
                    await self.emitter.send_log(f"Не удалось принять заявку от {name}. Ответ VK: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Завершено. Принято заявок: {processed_count}.", "success")
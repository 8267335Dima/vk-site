# backend/app/services/incoming_request_service.py
from typing import Dict, Any
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles

class IncomingRequestService(BaseVKService):
    async def accept_friend_requests(self, **kwargs):
        filters: Dict[str, Any] = kwargs.get('filters', {})
        return await self._execute_logic(self._accept_friend_requests_logic, filters)

    async def _accept_friend_requests_logic(self, filters: Dict[str, Any]):
        await self.emitter.send_log("Начинаем прием заявок в друзья...", "info")
        stats = await self._get_today_stats()
        
        response = await self.vk_api.get_incoming_friend_requests(extended=1)
        if not response or not response.get('items'):
            await self.emitter.send_log("Входящие заявки не найдены.", "info")
            return
        
        profiles = response.get('items', [])
        await self.emitter.send_log(f"Найдено {len(profiles)} заявок. Начинаем фильтрацию...", "info")
        
        filtered_profiles = apply_filters_to_profiles(profiles, filters)

        await self.emitter.send_log(f"После фильтрации осталось: {len(filtered_profiles)}.", "info")
        
        if not filtered_profiles:
            await self.emitter.send_log("Подходящих заявок для приема не найдено.", "success")
            return
        
        processed_count = 0
        batch_size = 25
        for i in range(0, len(filtered_profiles), batch_size):
            batch = filtered_profiles[i:i + batch_size]
            
            calls = [{"method": "friends.add", "params": {"user_id": p.get('id')}} for p in batch]

            await self.humanizer.imitate_simple_action()
            results = await self.vk_api.execute(calls)

            if results is None:
                await self.emitter.send_log("Пакетный запрос на принятие заявок не удался.", "error")
                continue

            for profile, result in zip(batch, results):
                user_id = profile.get('id')
                name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"
                
                if result in [1, 2, 4]:  # Коды успешного добавления от VK API
                    processed_count += 1
                    await self._increment_stat(stats, 'friend_requests_accepted_count')
                    await self.emitter.send_log(f"Принята заявка от {name}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', f'неизвестная ошибка, код {result}') if isinstance(result, dict) else f'код {result}'
                    await self.emitter.send_log(f"Не удалось принять заявку от {name}. Ответ VK: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Завершено. Принято заявок: {processed_count}.", "success")
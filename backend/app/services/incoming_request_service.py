from app.services.base import BaseVKService
from app.services.interfaces import IExecutableTask, IPreviewableTask
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AcceptFriendsRequest
from typing import List, Dict, Any

class IncomingRequestService(BaseVKService, IExecutableTask, IPreviewableTask):
    async def get_targets(self, params: AcceptFriendsRequest) -> List[Dict[str, Any]]:
        await self._initialize_vk_api()
        response = await self.vk_api.get_incoming_friend_requests(extended=1)
        if not response or not response.get('items'):
            return []
        profiles = response.get('items', [])
        return await apply_filters_to_profiles(profiles, params.filters)

    async def execute(self, params: AcceptFriendsRequest) -> str:
        await self._initialize_vk_api()
        await self.emitter.send_log("Начинаем прием заявок в друзья...", "info")
        stats = await self._get_today_stats()
        targets = await self.get_targets(params)
        if not targets:
            return "Подходящих заявок для приема не найдено."
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
                user_id, name, url = profile.get('id'), f"{profile.get('first_name', '')} {profile.get('last_name', '')}", f"https://vk.com/id{profile.get('id')}"
                if result in [1, 2, 4]:
                    processed_count += 1
                    await self._increment_stat(stats, 'friend_requests_accepted_count')
                    await self.emitter.send_log(f"Принята заявка от {name}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', f'код {result}') if isinstance(result, dict) else f'код {result}'
                    await self.emitter.send_log(f"Не удалось принять заявку от {name}. Ответ VK: {error_msg}", "error", target_url=url)
        return f"Завершено. Принято заявок: {processed_count}."
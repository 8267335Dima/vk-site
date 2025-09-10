# backend/app/services/incoming_request_service.py
from typing import Dict, Any, List
from app.services.base import BaseVKService

class IncomingRequestService(BaseVKService):
    async def accept_friend_requests(self, filters: Dict[str, Any]):
        return await self._execute_logic(self._accept_friend_requests_logic, filters)

    async def _accept_friend_requests_logic(self, filters: Dict[str, Any]):
        await self.emitter.send_log("Начинаем прием заявок в друзья...", "info")
        stats = await self._get_today_stats()
        
        response = await self.vk_api.get_incoming_friend_requests()
        if not response or not response.get('items'):
            await self.emitter.send_log("Входящие заявки не найдены.", "info")
            return
        
        # --- ИЗМЕНЕНИЕ: Получаем полные профили для расширенной фильтрации ---
        profiles = await self._get_user_profiles(response['items'])
        filtered_profiles = await self._apply_filters_to_profiles(profiles, filters)

        await self.emitter.send_log(f"Найдено {len(response['items'])} заявок. После фильтрации осталось: {len(filtered_profiles)}.", "info")
        
        processed_count = 0
        for profile in filtered_profiles:
            await self.humanizer.imitate_short_action_delay()
            user_id = profile['id']
            result = await self.vk_api.accept_friend_request(user_id)
            name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
            url = f"https://vk.com/id{user_id}"
            
            if result == 1:
                processed_count += 1
                await self._increment_stat(stats, 'friend_requests_accepted_count')
                await self.emitter.send_log(f"Принята заявка от {name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось принять заявку от {name}. Ответ VK: {result}", "error", target_url=url)
                
        await self.emitter.send_log(f"Завершено. Принято заявок: {processed_count}.", "success")

    async def _get_user_profiles(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        if not user_ids: return []
        user_profiles = []
        # --- ИЗМЕНЕНИЕ: Запрашиваем счетчики для фильтрации ---
        fields = "sex,online,last_seen,is_closed,status,counters"
        for i in range(0, len(user_ids), 1000):
            chunk = user_ids[i:i + 1000]
            ids_str = ",".join(map(str, chunk))
            profiles = await self.vk_api.get_user_info(user_ids=ids_str, fields=fields)
            if profiles: user_profiles.extend(profiles)
        return user_profiles

    async def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()
        for profile in profiles:
            # --- БАЗОВЫЕ ФИЛЬТРЫ ---
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True): continue
            if filters.get('sex') is not None and profile.get('sex') != filters['sex']: continue
            if filters.get('is_online', False) and not profile.get('online', 0): continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts: # Проверяем, есть ли информация
                last_seen_hours = filters.get('last_seen_hours')
                if last_seen_hours and (now_ts - last_seen_ts) > (last_seen_hours * 3600):
                    continue

            # --- НОВЫЕ ФИЛЬТРЫ по счетчикам ---
            counters = profile.get('counters', {})
            friends_count = counters.get('friends')
            followers_count = counters.get('followers')

            min_friends = filters.get('min_friends')
            if min_friends is not None and (friends_count is None or friends_count < min_friends):
                continue
            
            max_friends = filters.get('max_friends')
            if max_friends is not None and (friends_count is None or friends_count > max_friends):
                continue
                
            min_followers = filters.get('min_followers')
            if min_followers is not None and (followers_count is None or followers_count < min_followers):
                continue

            max_followers = filters.get('max_followers')
            if max_followers is not None and (followers_count is None or followers_count > max_followers):
                continue
            
            filtered_profiles.append(profile)
            
        return filtered_profiles
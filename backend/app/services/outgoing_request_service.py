# --- backend/app/services/outgoing_request_service.py ---
from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.db.models import DailyStats, FriendRequestLog, FriendRequestStatus
from sqlalchemy.dialects.postgresql import insert
from app.core.exceptions import UserLimitReachedError
from app.core.config import settings
from redis.asyncio import Redis as AsyncRedis

redis_lock_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)

class OutgoingRequestService(BaseVKService):
    async def add_recommended_friends(self, **kwargs):
        settings: Dict[str, Any] = kwargs
        count = settings.get('count', 20)
        filters = settings.get('filters', {})
        like_config = settings.get('like_config', {})
        send_message_on_add = settings.get('send_message_on_add', False)
        message_text = settings.get('message_text')
        
        return await self._execute_logic(self._add_recommended_friends_logic, count, filters, like_config, send_message_on_add, message_text)

    async def _add_recommended_friends_logic(self, count: int, filters: Dict[str, Any], like_config: Dict[str, Any], send_message_on_add: bool, message_text: str | None):
        await self.emitter.send_log(f"Начинаем добавление {count} друзей из рекомендаций...", "info")
        stats = await self._get_today_stats()
        
        response = await self.vk_api.get_recommended_friends(count=count * 3)
        if not response or not response.get('items'):
            await self.emitter.send_log("Рекомендации не найдены.", "warning")
            return

        filtered_profiles = self._apply_filters_to_profiles(response['items'], filters)
        await self.emitter.send_log(f"Найдено {len(response['items'])} рекомендаций. После фильтрации осталось: {len(filtered_profiles)}.", "info")
        
        processed_count = 0
        for profile in filtered_profiles:
            if processed_count >= count: break
            if stats.friends_added_count >= self.user.daily_add_friends_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит на отправку заявок ({self.user.daily_add_friends_limit}).")
            
            user_id = profile['id']
            
            lock_key = f"lock:add_friend:{self.user.id}:{user_id}"
            if not await redis_lock_client.set(lock_key, "1", ex=3600, nx=True):
                await self.emitter.send_log(f"Заявка пользователю {user_id} уже была отправлена недавно. Пропуск.", "debug")
                continue

            await self.humanizer.imitate_page_view()
            
            message = message_text.replace("{name}", profile.get("first_name", "")) if message_text and send_message_on_add else None
            result = await self.vk_api.add_friend(user_id, message) 
            
            name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
            url = f"https://vk.com/id{user_id}"
            
            if result in [1, 2, 4]:
                processed_count += 1
                await self._increment_stat(stats, 'friends_added_count')
                
                log_stmt = insert(FriendRequestLog).values(user_id=self.user.id, target_vk_id=user_id).on_conflict_do_nothing()
                await self.db.execute(log_stmt)

                log_msg = f"Отправлена заявка пользователю {name}"
                if send_message_on_add and message_text:
                    log_msg += " с сообщением."
                await self.emitter.send_log(log_msg, "success", target_url=url)
                
                if like_config.get('enabled') and not profile.get('is_closed', True):
                    await self._like_user_content(user_id, profile, like_config, stats)
            else:
                await self.emitter.send_log(f"Не удалось отправить заявку {name}. Ответ VK: {result}", "error", target_url=url)
                await redis_lock_client.delete(lock_key)

        await self.emitter.send_log(f"Завершено. Отправлено заявок: {processed_count}.", "success")

    async def _like_user_content(self, user_id: int, profile: Dict[str, Any], config: Dict[str, Any], stats: DailyStats):
        if stats.likes_count >= self.user.daily_likes_limit:
            await self.emitter.send_log("Достигнут дневной лимит лайков, пропуск лайкинга после добавления.", "warning")
            return

        targets = config.get('targets', [])
        
        if 'avatar' in targets and profile.get('photo_id'):
            photo_id_parts = profile['photo_id'].split('_')
            if len(photo_id_parts) == 2:
                photo_id = int(photo_id_parts[1])
                await self.humanizer.imitate_simple_action()
                res = await self.vk_api.add_like('photo', user_id, photo_id)
                if res and 'likes' in res:
                    await self._increment_stat(stats, 'likes_count')
                    await self.emitter.send_log(f"Поставлен лайк на аватар.", "success", target_url=f"https://vk.com/photo{user_id}_{photo_id}")

        if 'wall' in targets:
            wall = await self.vk_api.get_wall(owner_id=user_id, count=config.get('count', 1))
            if wall and wall.get('items'):
                for post in wall['items']:
                    if stats.likes_count >= self.user.daily_likes_limit: return
                    await self.humanizer.imitate_simple_action()
                    res = await self.vk_api.add_like('post', user_id, post['id'])
                    if res and 'likes' in res:
                        await self._increment_stat(stats, 'likes_count')
                        await self.emitter.send_log(f"Поставлен лайк на пост на стене.", "success", target_url=f"https://vk.com/wall{user_id}_{post['id']}")

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()
        for profile in profiles:
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True): continue
            if filters.get('sex') is not None and filters.get('sex') != 0 and profile.get('sex') != filters['sex']: continue
            if filters.get('is_online', False) and not profile.get('online', 0): continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts:
                last_seen_hours = filters.get('last_seen_hours')
                if last_seen_hours and (now_ts - last_seen_ts) > (last_seen_hours * 3600):
                    continue
            
            filtered_profiles.append(profile)
        return filtered_profiles
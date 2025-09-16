# --- backend/app/services/outgoing_request_service.py ---
from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.db.models import DailyStats, FriendRequestLog
from sqlalchemy.dialects.postgresql import insert
from app.core.exceptions import UserLimitReachedError
from app.core.config import settings
from redis.asyncio import Redis as AsyncRedis
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AddFriendsRequest, LikeAfterAddConfig

redis_lock_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)

class OutgoingRequestService(BaseVKService):

    async def get_add_recommended_targets(self, params: AddFriendsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает и фильтрует пользователей из рекомендаций.
        Этот метод используется как для предпросмотра, так и для реального выполнения.
        """
        # Берем с запасом, т.к. фильтрация может отсеять многих
        response = await self.vk_api.get_recommended_friends(count=params.count * 3)
        if not response or not response.get('items'):
            await self.emitter.send_log("Рекомендации не найдены.", "warning")
            return []

        await self.emitter.send_log(f"Найдено {len(response.get('items', []))} рекомендаций. Применяем фильтры...", "info")
        filtered_profiles = await apply_filters_to_profiles(response.get('items', []), params.filters)
        
        return filtered_profiles

    async def add_recommended_friends(self, params: AddFriendsRequest):
        return await self._execute_logic(self._add_recommended_friends_logic, params)

    async def _add_recommended_friends_logic(self, params: AddFriendsRequest):
        await self.emitter.send_log(f"Начинаем добавление до {params.count} друзей из рекомендаций...", "info")
        stats = await self._get_today_stats()

        # ШАГ 1: Получаем цели с помощью нового метода
        targets = await self.get_add_recommended_targets(params)
        
        await self.emitter.send_log(f"После фильтрации осталось: {len(targets)}. Начинаем отправку заявок.", "info")

        if not targets:
            await self.emitter.send_log("Подходящих пользователей для добавления не найдено.", "success")
            return

        processed_count = 0
        for profile in targets:
            if processed_count >= params.count: break
            if stats.friends_added_count >= self.user.daily_add_friends_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит на отправку заявок ({self.user.daily_add_friends_limit}).")
            
            user_id = profile.get('id')
            if not user_id: continue
            
            lock_key = f"lock:add_friend:{self.user.id}:{user_id}"
            if not await redis_lock_client.set(lock_key, "1", ex=3600, nx=True):
                continue

            await self.humanizer.read_and_scroll()
            
            message = params.message_text.replace("{name}", profile.get("first_name", "")) if params.message_text and params.send_message_on_add else None
            result = await self.vk_api.add_friend(user_id, message) 
            
            name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
            url = f"https://vk.com/id{user_id}"
            
            if result in [1, 2, 4]:
                processed_count += 1
                await self._increment_stat(stats, 'friends_added_count')
                
                log_stmt = insert(FriendRequestLog).values(user_id=self.user.id, target_vk_id=user_id).on_conflict_do_nothing()
                await self.db.execute(log_stmt)

                log_msg = f"Отправлена заявка пользователю {name}"
                if message:
                    log_msg += " с сообщением."
                await self.emitter.send_log(log_msg, "success", target_url=url)
                
                if params.like_config.enabled and not profile.get('is_closed', True):
                    await self._like_user_content(user_id, profile, params.like_config, stats)
            else:
                await self.emitter.send_log(f"Не удалось отправить заявку {name}. Ответ VK: {result}", "error", target_url=url)
                await redis_lock_client.delete(lock_key)

        await self.emitter.send_log(f"Завершено. Отправлено заявок: {processed_count}.", "success")

    async def _like_user_content(self, user_id: int, profile: Dict[str, Any], config: LikeAfterAddConfig, stats: DailyStats):
        if stats.likes_count >= self.user.daily_likes_limit:
            await self.emitter.send_log("Достигнут дневной лимит лайков, пропуск лайкинга после добавления.", "warning")
            return

        if 'avatar' in config.targets and profile.get('photo_id'):
            photo_id_parts = profile.get('photo_id', '').split('_')
            if len(photo_id_parts) == 2:
                photo_id = int(photo_id_parts[1])
                await self.humanizer.imitate_simple_action()
                if await self.vk_api.add_like('photo', user_id, photo_id):
                    await self._increment_stat(stats, 'likes_count')
                    await self.emitter.send_log(f"Поставлен лайк на аватар.", "success", target_url=f"https://vk.com/photo{user_id}_{photo_id}")

        if 'wall' in config.targets:
            wall = await self.vk_api.get_wall(owner_id=user_id, count=1)
            if wall and wall.get('items') and stats.likes_count < self.user.daily_likes_limit:
                post = wall['items'][0]
                await self.humanizer.imitate_simple_action()
                if await self.vk_api.add_like('post', user_id, post.get('id')):
                    await self._increment_stat(stats, 'likes_count')
                    await self.emitter.send_log(f"Поставлен лайк на пост на стене.", "success", target_url=f"https://vk.com/wall{user_id}_{post.get('id')}")
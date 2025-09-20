from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.db.models import DailyStats, FriendRequestLog
from sqlalchemy.dialects.postgresql import insert
from app.core.exceptions import UserLimitReachedError
from app.core.config import settings
from redis.asyncio import Redis as AsyncRedis
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AddFriendsRequest, LikeAfterAddConfig
from .interfaces import IExecutableTask, IPreviewableTask

class OutgoingRequestService(BaseVKService, IExecutableTask, IPreviewableTask):
    async def get_targets(self, params: AddFriendsRequest) -> List[Dict[str, Any]]:
        await self._initialize_vk_api()
        response = await self.vk_api.get_recommended_friends(count=params.count * 3)
        if not response or not response.get('items'):
            return []
        return await apply_filters_to_profiles(response.get('items', []), params.filters)

    async def execute(self, params: AddFriendsRequest) -> str:
        await self._initialize_vk_api()
        stats = await self._get_today_stats()
        targets = await self.get_targets(params)
        if not targets:
            return "Подходящих пользователей для добавления не найдено."
        redis_lock_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
        try:
            processed_count = 0
            for profile in targets:
                if processed_count >= params.count: break
                if stats.friends_added_count >= self.user.daily_add_friends_limit:
                    raise UserLimitReachedError(f"Достигнут дневной лимит заявок ({self.user.daily_add_friends_limit}).")
                user_id = profile.get('id')
                if not user_id: continue
                lock_key = f"lock:add_friend:{self.user.id}:{user_id}"
                if not await redis_lock_client.set(lock_key, "1", ex=3600, nx=True): continue
                await self.humanizer.think(action_type='add_friend')
                message = params.message_text.replace("{name}", profile.get("first_name", "")) if params.send_message_on_add and params.message_text else None
                result = await self.vk_api.add_friend(user_id, message)
                name, url = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(), f"https://vk.com/id{user_id}"
                if result in [1, 2, 4]:
                    processed_count += 1
                    await self._increment_stat(stats, 'friends_added_count')
                    if message: await self._increment_stat(stats, 'messages_sent_count')
                    log_stmt = insert(FriendRequestLog).values(user_id=self.user.id, target_vk_id=user_id).on_conflict_do_nothing()
                    await self.db.execute(log_stmt)
                    log_msg = f"Отправлена заявка пользователю {name}" + (" с сообщением." if message else "")
                    await self.emitter.send_log(log_msg, "success", target_url=url)
                    if params.like_config.enabled and not profile.get('is_closed', True):
                        await self._like_user_content(user_id, profile, params.like_config, stats)
                else:
                    await redis_lock_client.delete(lock_key)
            return f"Завершено. Отправлено заявок: {processed_count}."
        finally:
            await redis_lock_client.aclose()

    async def _like_user_content(self, user_id: int, profile: Dict[str, Any], config: LikeAfterAddConfig, stats: DailyStats):
        if stats.likes_count >= self.user.daily_likes_limit: return
        if 'avatar' in config.targets and profile.get('photo_id'):
            photo_id = int(profile['photo_id'].split('_')[1])
            await self.humanizer.think(action_type='like')
            if await self.vk_api.add_like('photo', user_id, photo_id):
                await self._increment_stat(stats, 'likes_count')
        if 'wall' in config.targets:
            wall = await self.vk_api.get_wall(owner_id=user_id, count=1)
            if wall and wall.get('items') and stats.likes_count < self.user.daily_likes_limit:
                post = wall['items'][0]
                await self.humanizer.think(action_type='like')
                if await self.vk_api.add_like('post', user_id, post.get('id')):
                    await self._increment_stat(stats, 'likes_count')
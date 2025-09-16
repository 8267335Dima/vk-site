# --- backend/app/services/feed_service.py ---
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import LikeFeedRequest

class FeedService(BaseVKService):

    async def like_newsfeed(self, params: LikeFeedRequest):
        return await self._execute_logic(self._like_newsfeed_logic, params)

    async def _like_newsfeed_logic(self, params: LikeFeedRequest):
        await self.emitter.send_log(f"Запуск задачи: поставить {params.count} лайков в ленте новостей.", "info")
        stats = await self._get_today_stats()
        
        newsfeed_filter = "photo" if params.filters.only_with_photo else "post"

        await self.humanizer.read_and_scroll()
        response = await self.vk_api.newsfeed.get(count=params.count * 2, filters=newsfeed_filter)

        if not response or not response.get('items'):
            await self.emitter.send_log("Посты в ленте не найдены. Задача завершена.", "warning")
            return

        posts = [p for p in response.get('items', []) if p.get('type') in ['post', 'photo']]
        await self.emitter.send_log(f"Найдено постов в ленте: {len(posts)}. Применяем фильтры...", "info")
        
        author_ids = [abs(p['source_id']) for p in posts if p.get('source_id', 0) > 0]
        
        filtered_author_ids = set(author_ids)
        if author_ids:
            author_profiles = await self._get_user_profiles(list(set(author_ids)))
            filtered_authors = await apply_filters_to_profiles(author_profiles, params.filters)
            filtered_author_ids = {a.get('id') for a in filtered_authors}

        processed_count = 0
        for item in posts:
            if processed_count >= params.count:
                break
            if stats.likes_count >= self.user.daily_likes_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит лайков ({self.user.daily_likes_limit}).")

            owner_id = item.get('source_id')
            item_id = item.get('post_id') or item.get('id')
            item_type = item.get('type')
            
            if not all([owner_id, item_id, item_type]) or item.get('likes', {}).get('user_likes') == 1:
                continue
                
            if owner_id > 0 and owner_id not in filtered_author_ids:
                continue

            url_prefix = "wall" if item_type == "post" else "photo"
            url = f"https://vk.com/{url_prefix}{owner_id}_{item_id}"

            await self.humanizer.think(action_type='like')
            result = await self.vk_api.likes.add(item_type, owner_id, item_id)
            
            if result and 'likes' in result:
                processed_count += 1
                await self._increment_stat(stats, 'likes_count')
                await self.emitter.send_log(f"Поставлен лайк ({processed_count}/{params.count})", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось поставить лайк. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков: {processed_count}.", "success")
        
    async def _get_user_profiles(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        if not user_ids: return []
        
        all_profiles = []
        for i in range(0, len(user_ids), 1000):
            chunk = user_ids[i:i + 1000]
            ids_str = ",".join(map(str, chunk))
            profiles = await self.vk_api.users.get(user_ids=ids_str)
            if profiles:
                all_profiles.extend(profiles)
        return all_profiles
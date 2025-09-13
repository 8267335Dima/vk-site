# --- backend/app/services/feed_service.py ---
import random
from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError
from app.services.vk_user_filter import apply_filters_to_profiles

class FeedService(BaseVKService):

    async def like_newsfeed(self, **kwargs):
        settings: Dict[str, Any] = kwargs
        count = settings.get('count', 50)
        filters = settings.get('filters', {})
        return await self._execute_logic(self._like_newsfeed_logic, count, filters)

    async def _like_newsfeed_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Запуск задачи: поставить {count} лайков в ленте новостей.", "info")
        stats = await self._get_today_stats()
        
        newsfeed_filter = "photo" if filters.get("only_with_photo") else "post"

        await self.humanizer.imitate_page_view()
        response = await self.vk_api.get_newsfeed(count=count * 2, filters=newsfeed_filter)

        if not response or not response.get('items'):
            await self.emitter.send_log("Посты в ленте не найдены.", "warning")
            return

        posts = [p for p in response.get('items', []) if p.get('type') in ['post', 'photo']]
        author_ids = [abs(p['source_id']) for p in posts if p.get('source_id', 0) > 0]
        
        filtered_author_ids = set(author_ids)
        if author_ids:
            author_profiles = await self._get_user_profiles(list(set(author_ids)))
            filtered_authors = apply_filters_to_profiles(author_profiles, filters)
            filtered_author_ids = {a.get('id') for a in filtered_authors}

        processed_count = 0
        for item in posts:
            if processed_count >= count:
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

            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.add_like(item_type, owner_id, item_id)
            
            if result and 'likes' in result:
                processed_count += 1
                await self._increment_stat(stats, 'likes_count')
                if processed_count % 10 == 0:
                    await self.emitter.send_log(f"Поставлено лайков: {processed_count}/{count}", "info")
            else:
                url = f"https://vk.com/wall{owner_id}_{item_id}"
                await self.emitter.send_log(f"Не удалось поставить лайк. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков: {processed_count}.", "success")
        
    async def _get_user_profiles(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        if not user_ids:
            return []
        
        all_profiles = []
        # Разделение на чанки по 1000 ID, как требует VK API
        for i in range(0, len(user_ids), 1000):
            chunk = user_ids[i:i + 1000]
            ids_str = ",".join(map(str, chunk))
            profiles = await self.vk_api.get_user_info(user_ids=ids_str)
            if profiles:
                all_profiles.extend(profiles)
        return all_profiles
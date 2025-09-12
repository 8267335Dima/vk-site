# backend/app/services/feed_service.py
import random
from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError

class FeedService(BaseVKService):

    async def like_newsfeed(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._like_newsfeed_logic, count, filters)

    async def _like_newsfeed_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Запуск задачи: поставить {count} лайков в ленте новостей.", "info")
        stats = await self._get_today_stats()
        filters['allow_closed_profiles'] = True

        await self.humanizer.imitate_page_view()
        response = await self.vk_api.get_newsfeed(count=count * 2)

        if not response or not response.get('items'):
            await self.emitter.send_log("Посты в ленте не найдены.", "warning")
            return

        posts = [p for p in response['items'] if p.get('type') == 'post']
        author_ids = [abs(p['source_id']) for p in posts if p.get('source_id') and p['source_id'] > 0]
        filtered_author_ids = set(author_ids)

        if author_ids:
            author_profiles = await self._get_user_profiles(list(set(author_ids)))
            filtered_authors = self._apply_filters_to_profiles(author_profiles, filters)
            filtered_author_ids = {a['id'] for a in filtered_authors}

        processed_count = 0
        for post in posts:
            if processed_count >= count:
                break
            if stats.likes_count >= self.user.daily_likes_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит лайков ({self.user.daily_likes_limit}).")

            owner_id = post.get('source_id')
            if not owner_id or post.get('likes', {}).get('user_likes') == 1:
                continue
            if owner_id > 0 and owner_id not in filtered_author_ids:
                continue

            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.add_like('post', owner_id, post['post_id'])
            
            if result and 'likes' in result:
                processed_count += 1
                await self._increment_stat(stats, 'likes_count')
                if processed_count % 10 == 0:
                     await self.emitter.send_log(f"Поставлено лайков: {processed_count}/{count}", "info")
            else:
                url = f"https://vk.com/wall{owner_id}_{post['post_id']}"
                await self.emitter.send_log(f"Не удалось поставить лайк. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков: {processed_count}.", "success")

    async def like_friends_feed(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._like_friends_feed_logic, count, filters)

    async def _like_friends_feed_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Запуск задачи: поставить {count} лайков на стенах друзей.", "info")
        stats = await self._get_today_stats()
        filters['allow_closed_profiles'] = True

        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen")
        if not friends_response:
            await self.emitter.send_log("Не удалось получить список друзей.", "error")
            return

        filtered_friends = self._apply_filters_to_profiles(friends_response, filters)
        if not filtered_friends:
            await self.emitter.send_log("После применения фильтров не осталось друзей для обработки.", "warning")
            return

        processed_likes = 0
        random.shuffle(filtered_friends)
        for friend in filtered_friends:
            if processed_likes >= count:
                break
            if stats.likes_count >= self.user.daily_likes_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит лайков ({self.user.daily_likes_limit}).")

            friend_id = friend['id']
            await self.humanizer.imitate_page_view()
            wall = await self.vk_api.get_wall(owner_id=friend_id, count=5)
            if not wall or not wall.get('items'):
                continue

            posts_to_like = [p for p in wall['items'] if p.get('likes', {}).get('user_likes') == 0]
            if not posts_to_like:
                continue

            post_to_like = random.choice(posts_to_like)
            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.add_like('post', friend_id, post_to_like['id'])
            
            if result and 'likes' in result:
                processed_likes += 1
                await self._increment_stat(stats, 'likes_count')
                await self._increment_stat(stats, 'like_friends_feed_count')
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/wall{friend_id}_{post_to_like['id']}"
                await self.emitter.send_log(f"Поставлен лайк другу {name} ({processed_likes}/{count})", "success", target_url=url)
            else:
                url = f"https://vk.com/wall{friend_id}_{post_to_like['id']}"
                await self.emitter.send_log(f"Не удалось поставить лайк другу. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков друзьям: {processed_likes}.", "success")
        
    async def _get_user_profiles(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        if not user_ids:
            return []
        user_profiles = []
        for i in range(0, len(user_ids), 1000):
            chunk = user_ids[i:i + 1000]
            ids_str = ",".join(map(str, chunk))
            profiles = await self.vk_api.get_user_info(user_ids=ids_str)
            if profiles:
                user_profiles.extend(profiles)
        return user_profiles

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()

        for profile in profiles:
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True):
                continue
            
            if filters.get('sex') and profile.get('sex') != filters['sex']:
                continue
            
            if filters.get('is_online', False) and not profile.get('online', 0):
                continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts == 0:
                continue

            last_seen_days = filters.get('last_seen_days')
            if last_seen_days and (now_ts - last_seen_ts) > (last_seen_days * 86400):
                continue

            filtered_profiles.append(profile)
            
        return filtered_profiles
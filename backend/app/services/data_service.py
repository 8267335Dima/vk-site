# backend/app/services/data_service.py
import json
import re
from typing import List, Dict, Any, AsyncGenerator
from app.services.base import BaseVKService
from app.api.schemas.data import ParsingFilters # Новая Pydantic-модель
from collections import Counter

class DataService(BaseVKService):

    async def parse_active_group_audience(self, group_id: int, filters: ParsingFilters) -> List[Dict[str, Any]]:
        """Собирает активную аудиторию (лайки/комментарии) с постов сообщества."""
        await self._initialize_vk_api()
        
        wall_response = await self.vk_api.wall.get(owner_id=-group_id, count=filters.posts_depth)
        if not wall_response or not wall_response.get('items'):
            return []

        active_user_ids = set()
        for post in wall_response['items']:
            post_id = post['id']
            # Собираем лайкнувших
            likes_resp = await self.vk_api.likes.getList(type='post', owner_id=-group_id, item_id=post_id)
            if likes_resp and likes_resp.get('items'):
                active_user_ids.update(likes_resp['items'])
            
            # Собираем комментаторов
            comments_resp = await self.vk_api.wall.getComments(owner_id=-group_id, post_id=post_id)
            if comments_resp and comments_resp.get('items'):
                active_user_ids.update(c['from_id'] for c in comments_resp['items'])

        if not active_user_ids:
            return []

        # Получаем профили собранных ID
        profiles = await self.vk_api.users.get(user_ids=",".join(map(str, list(active_user_ids)[:1000])))
        return profiles or []

    async def export_conversation_as_json(self, peer_id: int) -> AsyncGenerator[str, None]:
        """Экспортирует историю диалога в виде JSON-строк."""
        await self._initialize_vk_api()
        offset = 0
        count = 200
        
        yield '[\n' # Начало JSON-массива
        
        is_first_chunk = True
        while True:
            response = await self.vk_api.messages.getHistory(user_id=peer_id, count=count, offset=offset, rev=1)
            if not response or not response.get('items'):
                break

            items = response['items']
            for message in items:
                if not is_first_chunk:
                    yield ',\n'
                yield json.dumps(message, ensure_ascii=False, indent=2)
                is_first_chunk = False

            if len(items) < count:
                break
            offset += count
            
        yield '\n]\n' # Конец JSON-массива

    async def parse_group_members(self, group_id: int, count: int = 1000) -> List[Dict[str, Any]]:
        """Собирает подписчиков сообщества."""
        await self._initialize_vk_api()
        
        # Ограничиваем максимальное количество для одного запроса
        fetch_count = min(count, 1000)
        
        members_response = await self.vk_api.groups.getMembers(group_id=group_id, count=fetch_count, fields="sex,bdate,city,online")
        if not members_response or not members_response.get('items'):
            return []
            
        return members_response['items']

    async def parse_user_wall(self, user_id: int, count: int = 100) -> List[Dict[str, Any]]:
        """Собирает посты со стены указанного пользователя."""
        await self._initialize_vk_api()
        
        fetch_count = min(count, 100)
        
        wall_response = await self.vk_api.wall.get(owner_id=user_id, count=fetch_count)
        if not wall_response or not wall_response.get('items'):
            return []
            
        return wall_response['items']
    
    async def parse_top_active_users(
        self, group_id: int, posts_depth: int, top_n: int
    ) -> List[Dict[str, Any]]:
        """
        Собирает самых активных пользователей (лайки + комментарии) с последних постов
        сообщества и возвращает их рейтинг.
        """
        await self._initialize_vk_api()
        
        wall_response = await self.vk_api.wall.get(owner_id=-group_id, count=posts_depth)
        if not wall_response or not wall_response.get('items'):
            return []

        activity_scores = Counter()
        comment_weight = 2  # Комментарий считаем в 2 раза ценнее лайка
        like_weight = 1

        for post in wall_response['items']:
            post_id = post['id']
            # Собираем лайкнувших
            likes_resp = await self.vk_api.likes.getList(type='post', owner_id=-group_id, item_id=post_id)
            if likes_resp and likes_resp.get('items'):
                for user_id in likes_resp['items']:
                    activity_scores[user_id] += like_weight
            
            # Собираем комментаторов
            comments_resp = await self.vk_api.wall.getComments(owner_id=-group_id, post_id=post_id)
            if comments_resp and comments_resp.get('items'):
                for comment in comments_resp['items']:
                    # Исключаем комментарии от самого сообщества
                    if comment['from_id'] > 0:
                        activity_scores[comment['from_id']] += comment_weight
        
        if not activity_scores:
            return []

        # Находим N самых активных
        top_users_data = activity_scores.most_common(top_n)
        top_user_ids = [user_id for user_id, score in top_users_data]

        if not top_user_ids:
            return []

        # Получаем профили самых активных пользователей
        profiles = await self.vk_api.users.get(
            user_ids=",".join(map(str, top_user_ids)),
            fields="photo_100, online"
        )
        
        # Собираем финальный результат
        profiles_map = {p['id']: p for p in profiles}
        
        result = []
        for user_id, score in top_users_data:
            profile = profiles_map.get(user_id)
            if profile:
                result.append({
                    "user_info": profile,
                    "activity_score": score
                })
        
        return result
    
    async def parse_contacts_from_discussions(self, group_id: int, topic_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Парсит комментарии в указанных обсуждениях группы и извлекает из них ID пользователей.
        """
        await self._initialize_vk_api()
        
        user_ids = set()
        
        for topic_id in topic_ids:
            offset = 0
            while True:
                comments_resp = await self.vk_api.board.getComments(
                    group_id=group_id, topic_id=topic_id, count=100, offset=offset, extended=1
                )
                if not comments_resp or not comments_resp.get('items'):
                    break
                
                # Собираем ID авторов комментариев
                user_ids.update(c['from_id'] for c in comments_resp['items'] if c['from_id'] > 0)
                
                # Ищем ID в тексте комментариев (например, ссылки)
                for comment in comments_resp['items']:
                    found = re.findall(r"vk.com/(id\d+|\w+)", comment.get('text', ''))
                    # Здесь потребуется логика преобразования screen_name в ID,
                    # но для простоты пока оставим только ID
                    user_ids.update(int(uid[2:]) for uid in found if uid.startswith('id'))

                if len(comments_resp['items']) < 100:
                    break
                offset += 100
        
        if not user_ids:
            return []
            
        profiles = await self.vk_api.users.get(user_ids=",".join(map(str, list(user_ids)[:1000])))
        return profiles or []
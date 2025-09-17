# --- ЗАМЕНИТЬ ВЕСЬ ФАЙЛ ---
import datetime
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import ProfileMetric
from app.services.vk_api import VKAPIError
import structlog

log = structlog.get_logger(__name__)

class ProfileAnalyticsService(BaseVKService):

    async def snapshot_profile_metrics(self):
        """
        Собирает ключевые метрики профиля, включая ВСЕ и НЕДАВНИЕ лайки (раздельно),
        и сохраняет их в БД как "снимок" за текущий день.
        """
        try:
            await self._initialize_vk_api()
        except Exception as e:
            log.error("snapshot_metrics.init_failed", user_id=self.user.id, error=str(e))
            return

        # 1. Получаем счетчики
        user_info_list = await self.vk_api.users.get(user_ids=str(self.user.vk_id), fields="counters")
        counters = user_info_list[0].get('counters', {}) if user_info_list else {}
        wall_info = await self.vk_api.wall.get(owner_id=self.user.vk_id, count=0)
        wall_posts_count = wall_info.get('count', 0) if wall_info else 0

        # 2. <<< ИЗМЕНЕНО: Используем пользовательские настройки >>>
        recent_posts_to_check = self.user.analytics_settings_posts_count
        recent_photos_to_check = self.user.analytics_settings_photos_count
        
        # 3. Считаем лайки
        recent_post_likes, total_post_likes = await self._get_likes_from_wall(wall_posts_count, recent_posts_to_check)
        recent_photo_likes, total_photo_likes = await self._get_likes_from_photos(counters.get('photos', 0), recent_photos_to_check)

        # 4. Сохраняем все в БД
        today = datetime.date.today()
        stmt = insert(ProfileMetric).values(
            user_id=self.user.id, date=today,
            friends_count=counters.get('friends', 0),
            followers_count=counters.get('followers', 0),
            photos_count=counters.get('photos', 0),
            wall_posts_count=wall_posts_count,
            recent_post_likes=recent_post_likes,
            recent_photo_likes=recent_photo_likes,
            total_post_likes=total_post_likes,
            total_photo_likes=total_photo_likes,
        ).on_conflict_do_update(
            index_elements=['user_id', 'date'],
            set_={
                'friends_count': counters.get('friends', 0), 'followers_count': counters.get('followers', 0),
                'photos_count': counters.get('photos', 0), 'wall_posts_count': wall_posts_count,
                'recent_post_likes': recent_post_likes, 'recent_photo_likes': recent_photo_likes,
                'total_post_likes': total_post_likes, 'total_photo_likes': total_photo_likes,
            }
        )
        await self.db.execute(stmt)
        log.info("snapshot_metrics.success", user_id=self.user.id, total_post_likes=total_post_likes, total_photo_likes=total_photo_likes)

    async def _get_likes_from_wall(self, total_count: int, recent_count: int) -> tuple[int, int]:
        if total_count == 0:
            return 0, 0
        
        total_likes = 0
        recent_likes = 0
        offset = 0
        is_first_chunk = True
        
        while offset < total_count:
            try:
                chunk = await self.vk_api.wall.get(owner_id=self.user.vk_id, count=100, offset=offset)
                if not chunk or not chunk.get('items'):
                    break
                
                chunk_likes = sum(p.get('likes', {}).get('count', 0) for p in chunk['items'])
                total_likes += chunk_likes
                
                if is_first_chunk:
                    # Лайки с первой страницы всегда считаются "недавними" (до recent_count)
                    recent_items = chunk['items'][:recent_count]
                    recent_likes = sum(p.get('likes', {}).get('count', 0) for p in recent_items)
                    is_first_chunk = False

                offset += 100
            except VKAPIError as e:
                log.warn("snapshot.wall_likes_error", user_id=self.user.id, error=str(e))
                break
        return recent_likes, total_likes

    async def _get_likes_from_photos(self, total_count: int, recent_count: int) -> tuple[int, int]:
        if total_count == 0:
            return 0, 0

        total_likes = 0
        recent_likes = 0
        offset = 0
        is_first_chunk = True

        while offset < total_count:
            try:
                chunk = await self.vk_api.photos.getAll(owner_id=self.user.vk_id, count=200, offset=offset)
                if not chunk or not chunk.get('items'):
                    break
                
                chunk_likes = sum(p.get('likes', {}).get('count', 0) for p in chunk['items'])
                total_likes += chunk_likes

                if is_first_chunk:
                    recent_items = chunk['items'][:recent_count]
                    recent_likes = sum(p.get('likes', {}).get('count', 0) for p in recent_items)
                    is_first_chunk = False

                offset += 200
            except VKAPIError as e:
                log.warn("snapshot.photo_likes_error", user_id=self.user.id, error=str(e))
                break
        return recent_likes, total_likes
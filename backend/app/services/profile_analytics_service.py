# backend/app/services/profile_analytics_service.py
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
        Собирает ключевые метрики профиля (общее число лайков, друзья)
        и сохраняет их для построения графика роста.
        """
        try:
            await self._initialize_vk_api()
        except Exception as e:
            log.error("snapshot_metrics.init_failed", user_id=self.user.id, error=str(e))
            return

        total_likes = 0
        try:
            # 1. Считаем лайки на постах
            wall_posts = await self.vk_api.get_wall(owner_id=self.user.vk_id, count=100)
            if wall_posts and wall_posts.get('items'):
                total_likes += sum(post.get('likes', {}).get('count', 0) for post in wall_posts['items'])

            # 2. Считаем лайки на фотографиях
            photos = await self.vk_api.get_photos(owner_id=self.user.vk_id, count=200)
            if photos and photos.get('items'):
                total_likes += sum(photo.get('likes', {}).get('count', 0) for photo in photos['items'])
        except VKAPIError as e:
            log.warn("snapshot_metrics.likes_error", user_id=self.user.id, error=str(e))
            # Не прерываем выполнение, просто лайки будут 0

        # 3. Получаем количество друзей
        friends_count = 0
        try:
            user_info = await self.vk_api.get_user_info(user_ids=str(self.user.vk_id))
            if user_info and 'counters' in user_info:
                friends_count = user_info['counters'].get('friends', 0)
        except VKAPIError as e:
            log.error("snapshot_metrics.friends_error", user_id=self.user.id, error=str(e))
            return # Количество друзей - критически важный показатель, выходим если ошибка

        # 4. Сохраняем в БД
        today = datetime.date.today()
        stmt = insert(ProfileMetric).values(
            user_id=self.user.id,
            date=today,
            total_likes_on_content=total_likes,
            friends_count=friends_count
        ).on_conflict_do_update(
            index_elements=['user_id', 'date'],
            set_={
                'total_likes_on_content': total_likes,
                'friends_count': friends_count
            }
        )
        await self.db.execute(stmt)
        await self.db.commit()
        log.info("snapshot_metrics.success", user_id=self.user.id, likes=total_likes, friends=friends_count)
# --- backend/app/services/analytics_service.py ---
import datetime
import pytz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import PostActivityHeatmap
from app.services.vk_api import VKAPIError
import structlog

log = structlog.get_logger(__name__)

class AnalyticsService(BaseVKService):

    async def generate_post_activity_heatmap(self):
        await self._initialize_vk_api()
        
        try:
            friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="last_seen")
        except VKAPIError as e:
            log.error("heatmap.vk_error", user_id=self.user.id, error=str(e))
            return
        
        if not friends:
            return

        # Инициализируем матрицу 7 дней x 24 часа нулями
        heatmap = [[0 for _ in range(24)] for _ in range(7)]
        
        now = datetime.datetime.utcnow()
        # Анализируем активность за последние 2 недели
        two_weeks_ago = now - datetime.timedelta(weeks=2)

        for friend in friends:
            last_seen_data = friend.get("last_seen")
            if not last_seen_data:
                continue
            
            seen_timestamp = last_seen_data.get("time")
            if not seen_timestamp:
                continue
            
            seen_time = datetime.datetime.fromtimestamp(seen_timestamp, tz=pytz.UTC)
            
            if seen_time > two_weeks_ago:
                day_of_week = seen_time.weekday() # 0 = Понедельник, 6 = Воскресенье
                hour_of_day = seen_time.hour
                heatmap[day_of_week][hour_of_day] += 1
        
        # Нормализуем данные, чтобы получить значения от 0 до 100 для удобства фронтенда
        max_activity = max(max(row) for row in heatmap)
        if max_activity > 0:
            normalized_heatmap = [
                [int((count / max_activity) * 100) for count in row]
                for row in heatmap
            ]
        else:
            normalized_heatmap = heatmap
        
        stmt = insert(PostActivityHeatmap).values(
            user_id=self.user.id,
            heatmap_data={"data": normalized_heatmap},
        ).on_conflict_do_update(
            index_elements=['user_id'],
            set_={
                "heatmap_data": {"data": normalized_heatmap},
                "last_updated_at": datetime.datetime.utcnow()
            }
        )
        await self.db.execute(stmt)
        await self.db.commit()
        log.info("heatmap.generated", user_id=self.user.id)
# --- backend/app/services/analytics_service.py ---
import datetime
import pytz
from collections import Counter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import PostActivityHeatmap, User
from app.services.vk_api import VKAPIError
from app.api.schemas.analytics import AudienceAnalyticsResponse, AudienceStatItem, SexDistributionResponse
import structlog

log = structlog.get_logger(__name__)

# --- Вспомогательные функции, которые были в эндпоинте ---
def _calculate_age(bdate: str) -> int | None:
    try:
        parts = bdate.split('.')
        if len(parts) == 3:
            birth_date = datetime.datetime.strptime(bdate, "%d.%m.%Y")
            today = datetime.date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except (ValueError, TypeError):
        return None
    return None

def _get_age_group(age: int) -> str:
    if age < 18: return "< 18"
    if 18 <= age <= 24: return "18-24"
    if 25 <= age <= 34: return "25-34"
    if 35 <= age <= 44: return "35-44"
    if age >= 45: return "45+"
    return "Не указан"
# --- Конец вспомогательных функций ---


class AnalyticsService(BaseVKService):

    # --- НОВЫЙ МЕТОД, В КОТОРЫЙ ПЕРЕНЕСЕНА ВСЯ ЛОГИКА ---
    async def get_audience_distribution(self) -> AudienceAnalyticsResponse:
        """
        Получает друзей пользователя из VK и рассчитывает распределение
        по городам, возрасту и полу.
        """
        await self._initialize_vk_api()
        
        friends = await self.vk_api.get_user_friends(user_id=self.user.vk_id, fields="sex,bdate,city")
        if not friends:
            return AudienceAnalyticsResponse(city_distribution=[], age_distribution=[], sex_distribution=[])

        # Расчет по городам
        city_counter = Counter(
            friend['city']['title']
            for friend in friends
            if friend.get('city') and friend.get('city', {}).get('title') and not friend.get('deactivated')
        )
        top_cities = [
            AudienceStatItem(name=city, value=count)
            for city, count in city_counter.most_common(5)
        ]

        # Расчет по возрасту
        ages = [_calculate_age(friend['bdate']) for friend in friends if friend.get('bdate') and not friend.get('deactivated')]
        age_groups = [_get_age_group(age) for age in ages if age is not None]
        age_counter = Counter(age_groups)
        age_distribution = [
            AudienceStatItem(name=group, value=count)
            for group, count in sorted(age_counter.items())
        ]

        # Расчет по полу
        sex_counter = Counter(
            'Мужчины' if f.get('sex') == 2 else ('Женщины' if f.get('sex') == 1 else 'Не указан')
            for f in friends if not f.get('deactivated')
        )
        sex_distribution = [SexDistributionResponse(name=k, value=v) for k, v in sex_counter.items()]

        return AudienceAnalyticsResponse(
            city_distribution=top_cities,
            age_distribution=age_distribution,
            sex_distribution=sex_distribution
        )
    # --- КОНЕЦ НОВОГО МЕТОДА ---

    async def generate_post_activity_heatmap(self):
        await self._initialize_vk_api()
        
        try:
            friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="last_seen")
        except VKAPIError as e:
            log.error("heatmap.vk_error", user_id=self.user.id, error=str(e))
            return
        
        if not friends:
            return

        heatmap = [[0 for _ in range(24)] for _ in range(7)]
        now = datetime.datetime.utcnow()
        two_weeks_ago = now - datetime.timedelta(weeks=2)

        for friend in friends:
            last_seen_data = friend.get("last_seen")
            if not last_seen_data or not (seen_timestamp := last_seen_data.get("time")):
                continue
            
            seen_time = datetime.datetime.fromtimestamp(seen_timestamp, tz=pytz.UTC)
            
            if seen_time > two_weeks_ago:
                heatmap[seen_time.weekday()][seen_time.hour] += 1
        
        max_activity = max(max(row) for row in heatmap)
        normalized_heatmap = heatmap
        if max_activity > 0:
            normalized_heatmap = [[int((count / max_activity) * 100) for count in row] for row in heatmap]
        
        stmt = insert(PostActivityHeatmap).values(
            user_id=self.user.id,
            heatmap_data={"data": normalized_heatmap},
        ).on_conflict_do_update(
            index_elements=['user_id'],
            set_={"heatmap_data": {"data": normalized_heatmap}, "last_updated_at": datetime.datetime.utcnow()}
        )
        await self.db.execute(stmt)
        await self.db.commit()
        log.info("heatmap.generated", user_id=self.user.id)
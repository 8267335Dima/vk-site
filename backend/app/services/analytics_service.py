# backend/app/services/analytics_service.py
import datetime
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import FriendsHistory

class AnalyticsService(BaseVKService):

    async def snapshot_friends_count(self):
        await self._initialize_vk_api()
        
        user_info = await self.vk_api.get_user_info(user_ids=str(self.user.vk_id))
        if not user_info or 'counters' not in user_info:
            return

        friends_count = user_info['counters'].get('friends', 0)
        today = datetime.date.today()

        stmt = insert(FriendsHistory).values(
            user_id=self.user.id,
            date=today,
            friends_count=friends_count
        ).on_conflict_do_update(
            index_elements=['user_id', 'date'],
            set_={'friends_count': friends_count}
        )

        await self.db.execute(stmt)
        await self.db.commit()
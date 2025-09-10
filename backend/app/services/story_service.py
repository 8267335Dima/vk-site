# backend/app/services/story_service.py
from typing import Dict, Any
from app.services.base import BaseVKService

class StoryService(BaseVKService):

    async def view_stories(self, filters: Dict[str, Any]):
        return await self._execute_logic(self._view_stories_logic, filters)

    async def _view_stories_logic(self, filters: Dict[str, Any]):
        await self.humanizer.imitate_page_view()
        await self.emitter.send_log("Начинаем просмотр историй...", "info")
        stats = await self._get_today_stats()

        response = await self.vk_api.get_stories()
        if not response or not response.get('items'):
            await self.emitter.send_log("Новых историй не найдено.", "info")
            return
        
        total_stories_count = sum(len(group.get('stories', [])) for group in response['items'])
        if total_stories_count == 0:
            await self.emitter.send_log("Новых историй не найдено.", "info")
            return

        await self.emitter.send_log(f"Найдено {total_stories_count} новых историй.", "info")
        await self._increment_stat(stats, 'stories_viewed_count', total_stories_count)
        await self.emitter.send_log(f"Успешно просмотрено {total_stories_count} историй.", "success")
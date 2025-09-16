# backend/app/services/story_service.py
from app.services.base import BaseVKService
from app.api.schemas.actions import EmptyRequest

class StoryService(BaseVKService):

    async def view_stories(self, params: EmptyRequest):
        return await self._execute_logic(self._view_stories_logic)

    async def _view_stories_logic(self):
        await self.humanizer.read_and_scroll()
        await self.emitter.send_log("Начинаем просмотр историй...", "info")
        stats = await self._get_today_stats()

        response = await self.vk_api.stories.get()
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
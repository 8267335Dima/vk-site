from app.services.base import BaseVKService
from app.api.schemas.actions import EmptyRequest
from .interfaces import IExecutableTask

class StoryService(BaseVKService, IExecutableTask):
    async def execute(self, params: EmptyRequest) -> str:
        await self._initialize_vk_api()
        await self.humanizer.read_and_scroll()
        stats = await self._get_today_stats()
        response = await self.vk_api.stories.get()
        if not response or not response.get('items'):
            return "Новых историй не найдено."
        total_stories_count = sum(len(group.get('stories', [])) for group in response['items'])
        if total_stories_count == 0:
            return "Новых историй не найдено."
        await self._increment_stat(stats, 'stories_viewed_count', total_stories_count)
        return f"Успешно просмотрено {total_stories_count} историй."
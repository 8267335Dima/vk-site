# tests/services/test_services_robustness.py

import pytest
from unittest.mock import AsyncMock

from app.services.automation_service import AutomationService
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.api.schemas.actions import BirthdayCongratulationRequest

pytestmark = pytest.mark.anyio

@pytest.fixture
def mock_emitter(mocker):
    """Фикстура для мока эмиттера."""
    emitter = mocker.MagicMock()
    emitter.send_log = AsyncMock()
    return emitter

class TestAutomationServiceRobustness:

    async def test_birthday_congratulator_handles_friends_without_bdate(
        self, test_user, db_session, mock_emitter, mocker
    ):
        """
        Тест: Проверяет, что сервис поздравлений не падает, если у друзей
        в VK не указана дата рождения (`bdate`).
        """
        # Arrange
        service = AutomationService(db=db_session, user=test_user, emitter=mock_emitter)
        mock_vk_api = AsyncMock()
        # VK API возвращает друзей, но ни у одного нет поля 'bdate'
        mock_vk_api.get_user_friends.return_value = {
            "items": [
                {"id": 1, "first_name": "No Bdate"},
                {"id": 2, "first_name": "Also No Bdate"}
            ]
        }
        service.vk_api = mock_vk_api

        # Act
        # Вызываем метод получения целей для поздравления
        targets = await service.get_birthday_congratulation_targets(BirthdayCongratulationRequest())

        # Assert
        # Ожидаем пустой список, так как именинников нет
        assert targets == []
        # Проверяем, что не было лишних вызовов (например, к сервису сообщений)
        mock_emitter.send_log.assert_any_call("Найдено именинников: 0 чел. Применяем фильтры...", "info")

class TestProfileAnalyticsServiceRobustness:

    async def test_snapshot_handles_empty_counters_and_wall(
        self, test_user, db_session, mock_emitter, mocker
    ):
        """
        Тест: Проверяет, что сборщик метрик (`snapshot_profile_metrics`)
        корректно отрабатывает для нового пользователя, у которого нет
        ни постов, ни фотографий, ни счетчиков.
        """
        # Arrange
        service = ProfileAnalyticsService(db=db_session, user=test_user, emitter=mock_emitter)
        mock_vk_api = AsyncMock()
        # Мокаем ответы VK API, имитируя "пустой" аккаунт
        mock_vk_api.users.get.return_value = [{"id": test_user.vk_id}] # нет поля 'counters'
        mock_vk_api.wall.get.return_value = {"count": 0} # нет поля 'items'
        mock_vk_api.photos.getAll.return_value = None # API может вернуть None
        service.vk_api = mock_vk_api
        
        # Act & Assert
        # Мы ожидаем, что метод выполнится без ошибок
        try:
            await service.snapshot_profile_metrics()
        except Exception as e:
            pytest.fail(f"snapshot_profile_metrics failed unexpectedly on empty data: {e}")

        # Проверяем, что методы для подсчета лайков были вызваны, но вернули 0
        total_post_likes = await service._get_likes_from_wall(0, 100)
        assert total_post_likes == (0, 0)
        total_photo_likes = await service._get_likes_from_photos(0, 200)
        assert total_photo_likes == (0, 0)
# tests/services/vk_api/test_api_wrapper_methods.py

import pytest
from unittest.mock import AsyncMock

from app.services.vk_api import VKAPI

pytestmark = pytest.mark.asyncio

class TestVkApiWrapperMethods:

    @pytest.fixture
    def mock_vk_api(self, mocker) -> tuple[VKAPI, AsyncMock]:
        """Фикстура для создания VKAPI с моком _make_request."""
        mock_request = mocker.patch("app.services.vk_api.VKAPI._make_request", new_callable=AsyncMock)
        api = VKAPI(access_token="test_token")
        return api, mock_request

    async def test_wall_delete_method(self, mock_vk_api: tuple[VKAPI, AsyncMock]):
        """Тест: проверяет, что `wall.delete` формирует правильный вызов."""
        api, mock_request = mock_vk_api
        await api.wall.delete(post_id=123, owner_id=-456)
        
        mock_request.assert_awaited_once_with(
            "wall.delete",
            params={"post_id": 123, "owner_id": -456}
        )

    async def test_messages_mark_as_read_method(self, mock_vk_api: tuple[VKAPI, AsyncMock]):
        """Тест: проверяет, что `messages.markAsRead` формирует правильный вызов."""
        api, mock_request = mock_vk_api
        await api.messages.markAsRead(peer_id=987)
        
        mock_request.assert_awaited_once_with(
            "messages.markAsRead",
            params={"peer_id": 987}
        )

    async def test_photos_get_all_method(self, mock_vk_api: tuple[VKAPI, AsyncMock]):
        """Тест: проверяет, что `photos.getAll` добавляет параметр `extended=1`."""
        api, mock_request = mock_vk_api
        await api.photos.getAll(owner_id=111, count=50)
        
        mock_request.assert_awaited_once_with(
            "photos.getAll",
            params={"owner_id": 111, "count": 50, "extended": 1}
        )
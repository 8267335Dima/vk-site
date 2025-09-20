# tests/api/test_groups_api.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.db.models import User, Group, DailyStats
from app.core.security import encrypt_data

pytestmark = pytest.mark.anyio

@pytest.fixture
async def managed_group(db_session: AsyncSession, test_user: User) -> Group:
    """Фикстура для создания управляемой группы в БД."""
    group = Group(
        vk_group_id=123,
        name="Test Group",
        admin_user_id=test_user.id,
        encrypted_access_token=encrypt_data("fake_group_token")
    )
    db_session.add(group)
    await db_session.commit()
    return group

async def test_post_to_group_wall_respects_daily_limit(
    async_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
    managed_group: Group
):
    """
    Тест: проверяет, что эндпоинт публикации на стене группы
    возвращает ошибку 429, если дневной лимит постов исчерпан.
    """
    # Arrange: устанавливаем лимит в 5 постов и говорим, что сегодня уже было 5.
    test_user.daily_posts_limit = 5
    stats = DailyStats(user_id=test_user.id, posts_created_count=5)
    db_session.add(stats)
    await db_session.merge(test_user)
    await db_session.commit()

    post_data = {"message": "Этот пост не должен быть опубликован"}

    # Act
    response = await async_client.post(
        f"/api/v1/groups/{managed_group.id}/wall",
        headers=auth_headers,
        json=post_data
    )

    # Assert
    assert response.status_code == 429 # Too Many Requests
    assert "Достигнут дневной лимит" in response.json()["detail"]

async def test_upload_image_to_group_wall(
    async_client: AsyncClient,
    auth_headers: dict,
    managed_group: Group,
    mocker
):
    """
    Тест: проверяет эндпоинт загрузки изображения на стену группы.
    Взаимодействие с VK API полностью мокируется.
    """
    # Arrange
    mock_vk_api_class = mocker.patch("app.api.endpoints.groups.VKAPI")
    mock_instance = mock_vk_api_class.return_value
    mock_instance.photos.upload_for_wall = AsyncMock(return_value="photo-123_456")
    mock_instance.close = AsyncMock()
    
    file_content = b"fake image bytes"
    files = {"image": ("test.png", file_content, "image/png")}

    # Act
    response = await async_client.post(
        f"/api/v1/groups/{managed_group.id}/upload-image-file",
        headers=auth_headers,
        files=files
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == {"attachment_id": "photo-123_456"}
    # Проверяем, что VKAPI был инициализирован с токеном группы
    mock_vk_api_class.assert_called_with(access_token="fake_group_token")
    # Проверяем, что метод загрузки был вызван с байтами нашего файла
    mock_instance.photos.upload_for_wall.assert_awaited_with(file_content)
# tests/api/test_posts.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock

from app.db.models import User, ScheduledPost, DailyStats

# Все тесты в этом файле должны использовать anyio
pytestmark = pytest.mark.anyio


async def test_schedule_batch_posts_success(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест успешного пакетного планирования постов.
    """
    publish_time_1 = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    publish_time_2 = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    
    posts_data = {
        "posts": [
            {"post_text": "Первый тестовый пост", "publish_at": publish_time_1},
            {"post_text": "Второй тестовый пост", "attachments": ["photo1_1"], "publish_at": publish_time_2},
        ]
    }

    response = await async_client.post("/api/v1/posts/schedule-batch", headers=auth_headers, json=posts_data)

    assert response.status_code == 201
    response_data = response.json()
    assert len(response_data) == 2
    assert "arq_job_id" in response_data[0] and response_data[0]["arq_job_id"] is not None


async def test_schedule_batch_posts_limit_exceeded(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест на ошибку при превышении дневного лимита на создание постов.
    """
    test_user.daily_posts_limit = 10
    stats = DailyStats(user_id=test_user.id, posts_created_count=9)
    db_session.add(stats)
    await db_session.merge(test_user)
    await db_session.flush()

    posts_data = {
        "posts": [
            {"post_text": "Пост 1", "publish_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
            {"post_text": "Пост 2", "publish_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat()},
        ]
    }

    response = await async_client.post("/api/v1/posts/schedule-batch", headers=auth_headers, json=posts_data)

    assert response.status_code == 429


async def test_upload_image_from_file(async_client: AsyncClient, auth_headers: dict, mocker):
    """Тест на успешную загрузку изображения из файла."""
    # 1. Mock: Патчим класс VKAPI, а не его метод
    mock_vk_api_class = mocker.patch("app.api.endpoints.posts.VKAPI")
    mock_instance = mock_vk_api_class.return_value
    
    # 2. Настраиваем асинхронный мок для нужного метода на мок-экземпляре
    mock_instance.photos.upload_for_wall = AsyncMock(return_value="photo123_456")
    mock_instance.close = AsyncMock()

    # 3. Act: Формируем и отправляем запрос с файлом
    file_content = b"this is a fake image content"
    files = {"image": ("test.jpg", file_content, "image/jpeg")}
    
    response = await async_client.post(
        "/api/v1/posts/upload-image-file", headers=auth_headers, files=files
    )

    # 4. Assert: Проверяем ответ
    assert response.status_code == 200
    assert response.json() == {"attachment_id": "photo123_456"}


async def test_upload_image_from_url(async_client: AsyncClient, auth_headers: dict, mocker):
    """Тест на успешную загрузку изображения по URL."""
    # 1. Mock: Мокаем вспомогательную функцию скачивания
    mock_download = mocker.patch(
        "app.api.endpoints.posts._download_image_from_url",
        return_value=b"downloaded fake content"
    )
    
    # 2. Mock: Патчим класс VKAPI, а не его метод
    mock_vk_api_class = mocker.patch("app.api.endpoints.posts.VKAPI")
    mock_instance = mock_vk_api_class.return_value
    
    # 3. Настраиваем асинхронный мок для нужного метода на мок-экземпляре
    mock_instance.photos.upload_for_wall = AsyncMock(return_value="photo789_123")
    mock_instance.close = AsyncMock()
    
    # 4. Act: Отправляем запрос с URL
    request_data = {"image_url": "http://example.com/image.jpg"}
    response = await async_client.post(
        "/api/v1/posts/upload-image-from-url", headers=auth_headers, json=request_data
    )

    # 5. Assert: Проверяем ответ и что наши моки были вызваны
    assert response.status_code == 200
    assert response.json() == {"attachment_id": "photo789_123"}
    mock_download.assert_called_once_with("http://example.com/image.jpg")
    # Проверяем, что метод на мок-экземпляре был вызван с правильными данными
    mock_instance.photos.upload_for_wall.assert_awaited_once_with(b"downloaded fake content")
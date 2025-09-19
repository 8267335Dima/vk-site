# --- START OF FILE tests/api/test_posts.py ---

import aiohttp
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock

from app.db.models import User, ScheduledPost, DailyStats

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
    mock_vk_api_class = mocker.patch("app.api.endpoints.posts.VKAPI")
    mock_instance = mock_vk_api_class.return_value
    mock_instance.photos.upload_for_wall = AsyncMock(return_value="photo123_456")
    mock_instance.close = AsyncMock()

    file_content = b"this is a fake image content"
    files = {"image": ("test.jpg", file_content, "image/jpeg")}
    
    response = await async_client.post(
        "/api/v1/posts/upload-image-file", headers=auth_headers, files=files
    )

    assert response.status_code == 200
    assert response.json() == {"attachment_id": "photo123_456"}


async def test_upload_image_from_url(async_client: AsyncClient, auth_headers: dict, mocker):
    """Тест на успешную загрузку изображения по URL."""
    mock_download = mocker.patch(
        "app.api.endpoints.posts._download_image_from_url",
        return_value=b"downloaded fake content"
    )
    
    mock_vk_api_class = mocker.patch("app.api.endpoints.posts.VKAPI")
    mock_instance = mock_vk_api_class.return_value
    mock_instance.photos.upload_for_wall = AsyncMock(return_value="photo789_123")
    mock_instance.close = AsyncMock()
    
    request_data = {"image_url": "http://example.com/image.jpg"}
    response = await async_client.post(
        "/api/v1/posts/upload-image-from-url", headers=auth_headers, json=request_data
    )

    assert response.status_code == 200
    assert response.json() == {"attachment_id": "photo789_123"}
    mock_download.assert_called_once_with("http://example.com/image.jpg")
    mock_instance.photos.upload_for_wall.assert_awaited_once_with(b"downloaded fake content")

# НОВЫЙ ПАРАМЕТРИЗОВАННЫЙ ТЕСТ
@pytest.mark.parametrize(
    "json_payload, expected_status_code, expected_detail_substring",
    [
        (
            {"posts": [{"post_text": "My post", "publish_at": "invalid-date-format"}]},
            422,
            "Input should be a valid datetime or date",
        ),
        (
            {"posts": []}, # Пустой список постов
            400,
            "Список постов для планирования не может быть пустым",
        ),
        (
            {"wrong_key": "some_value"}, # Неправильный ключ в JSON
            422,
            "Field required",
        ),
    ],
)
async def test_schedule_batch_posts_validation_errors(
    async_client: AsyncClient, auth_headers: dict,
    json_payload: dict, expected_status_code: int, expected_detail_substring: str
):
    """
    Тест проверяет, что API возвращает ошибки валидации на некорректные данные.
    """
    response = await async_client.post(
        "/api/v1/posts/schedule-batch", headers=auth_headers, json=json_payload
    )

    assert response.status_code == expected_status_code
    # Проверяем, что в тексте ошибки есть ожидаемая фраза
    assert expected_detail_substring in str(response.json()["detail"])

async def test_upload_image_from_url_download_failure(async_client: AsyncClient, auth_headers: dict, mocker):
    """
    Тест на ошибку, если не удалось скачать изображение по URL.
    Сервер должен вернуть ошибку 400 Bad Request.
    """
    # Мокаем функцию скачивания, чтобы она выбрасывала исключение
    mocker.patch(
        "app.api.endpoints.posts._download_image_from_url",
        side_effect=aiohttp.ClientError("Could not connect")
    )
    
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Мы должны мокать класс VKAPI и настроить его экземпляр
    mock_vk_api_class = mocker.patch("app.api.endpoints.posts.VKAPI")
    mock_instance = mock_vk_api_class.return_value
    # Явно делаем метод close асинхронным
    mock_instance.close = AsyncMock()
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    
    request_data = {"image_url": "http://invalid-url-that-will-fail.com/image.jpg"}
    response = await async_client.post(
        "/api/v1/posts/upload-image-from-url", headers=auth_headers, json=request_data
    )

    assert response.status_code == 400
    assert "Не удалось скачать изображение по URL" in response.json()["detail"]
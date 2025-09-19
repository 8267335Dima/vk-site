# tests/services/test_vk_api_client.py

import pytest
import asyncio
from unittest.mock import AsyncMock

from app.services.vk_api import VKAPI, VKAPIError, VKFloodControlError

pytestmark = pytest.mark.anyio


async def test_vk_api_execute_method_builds_correct_code(mocker):
    """Тест проверяет, что метод execute правильно формирует JS-подобный код."""
    # Arrange
    # Мокаем метод _make_request, так как нам не важен его результат,
    # а только то, с какими параметрами он будет вызван.
    mocked_request = mocker.patch("app.services.vk_api.VKAPI._make_request", new_callable=AsyncMock)
    
    vk_api = VKAPI("test_token")

    calls = [
        {"method": "users.get", "params": {"user_ids": "1,2"}},
        {"method": "wall.post", "params": {"owner_id": -123, "message": "Привет, мир!"}},
    ]
    
    # Act
    await vk_api.execute(calls)

    # Assert
    # Проверяем, что _make_request был вызван с правильным кодом
    mocked_request.assert_called_once()
    args, kwargs = mocked_request.call_args
    sent_params = kwargs.get("params", {})
    
    expected_code_part1 = 'API.users.get({"user_ids": "1,2"})'
    expected_code_part2 = 'API.wall.post({"owner_id": -123, "message": "Привет, мир!"})'
    
    assert "code" in sent_params
    assert expected_code_part1 in sent_params["code"]
    assert expected_code_part2 in sent_params["code"]
    assert sent_params["code"].startswith("return [") and sent_params["code"].endswith("];")

    await vk_api.close()


async def test_make_request_retries_on_flood_control(mocker):
    """
    Тест проверяет, что клиент VK API делает повторную попытку при получении
    ошибки 'Too many requests' или 'Flood control'.
    """
    # Arrange
    # Мокаем post-запрос на уровне aiohttp
    mock_response = AsyncMock()
    mock_response.json.side_effect = [
        {"error": {"error_code": 9, "error_msg": "Flood control"}},
        {"response": {"status": "ok"}}
    ]
    mock_response.content_type = 'application/json'
    
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__.return_value = mock_response
    
    mocker.patch("aiohttp.ClientSession.post", return_value=mock_post_context)
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)

    vk_api = VKAPI("test_token")

    # Act
    response = await vk_api._make_request("some.method")

    # Assert
    assert response == {"status": "ok"}
    assert mock_response.json.call_count == 2
    
    await vk_api.close()


async def test_make_request_fails_after_all_retries(mocker):
    """
    Тест проверяет, что клиент падает с ошибкой, если все попытки не увенчались успехом.
    """
    # Arrange
    mock_response = AsyncMock()
    mock_response.json.return_value = {"error": {"error_code": 6, "error_msg": "Too many requests per second"}}
    mock_response.content_type = 'application/json'

    mock_post_context = AsyncMock()
    mock_post_context.__aenter__.return_value = mock_response

    mocker.patch("aiohttp.ClientSession.post", return_value=mock_post_context)
    mocker.patch("asyncio.sleep", new_callable=AsyncMock)
    
    vk_api = VKAPI("test_token")

    # Act & Assert
    with pytest.raises(VKFloodControlError):
        await vk_api._make_request("some.method")
    
    assert mock_response.json.call_count == 3
    
    await vk_api.close()


async def test_make_request_handles_non_json_response(mocker):
    """
    Тест проверяет, что клиент корректно обрабатывает ситуацию, когда VK
    возвращает HTML-страницу вместо JSON (например, при сбоях).
    """
    # Arrange
    mock_response = AsyncMock()
    mock_response.content_type = 'text/html'
    # Мокаем асинхронный метод text()
    mock_response.text = AsyncMock(return_value="<html><body>VK is down</body></html>")
    mock_response.status = 503
    
    mock_post_context = AsyncMock()
    mock_post_context.__aenter__.return_value = mock_response
    
    mocker.patch("aiohttp.ClientSession.post", return_value=mock_post_context)

    vk_api = VKAPI("test_token")

    # Act & Assert
    with pytest.raises(VKAPIError) as exc_info:
        await vk_api._make_request("some.method")
        
    # Проверяем, что сообщение об ошибке содержит нужный текст
    assert "не-JSON ответ" in str(exc_info.value)
    
    await vk_api.close()
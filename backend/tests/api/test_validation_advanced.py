# tests/api/test_validation_advanced.py

import pytest
from httpx import AsyncClient
from app.core.enums import TaskKey

pytestmark = pytest.mark.anyio

class TestAdvancedValidation:

    @pytest.mark.parametrize("payload, should_pass", [
        # Успешный кейс: флаг включен, текст есть
        ({"send_message_on_add": True, "message_text": "Привет!"}, True),
        # Неуспешный кейс: флаг включен, текста нет
        ({"send_message_on_add": True, "message_text": ""}, False),
        # Неуспешный кейс: флаг включен, текст из пробелов
        ({"send_message_on_add": True, "message_text": "   "}, False),
        # Успешный кейс: флаг выключен, текста нет
        ({"send_message_on_add": False, "message_text": None}, True),
    ])
    async def test_add_friends_message_validation(
        self, async_client: AsyncClient, auth_headers: dict, payload: dict, should_pass: bool
    ):
        """
        Тест проверяет валидацию @model_validator в схеме AddFriendsRequest:
        текст сообщения обязателен, только если включена опция его отправки.
        """
        # Arrange
        task_key = TaskKey.ADD_RECOMMENDED
        # Дополняем payload обязательными полями для Pydantic-модели
        full_payload = {"count": 1, "filters": {}, **payload}

        # Act
        response = await async_client.post(
            f"/api/v1/tasks/run/{task_key.value}",
            headers=auth_headers,
            json=full_payload
        )

        # Assert
        if should_pass:
            # Ожидаем 200, так как задача успешно поставлена в очередь
            assert response.status_code == 200
        else:
            # Ожидаем 422, так как валидация модели не пройдена
            assert response.status_code == 422
            assert "Текст сообщения не может быть пустым" in str(response.json())
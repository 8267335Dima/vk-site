# tests/api/test_validation.py

import pytest
from httpx import AsyncClient

from app.core.enums import TaskKey

pytestmark = pytest.mark.anyio

async def test_mass_messaging_attachments_limit(
    async_client: AsyncClient, auth_headers: dict
):
    """
    Тест проверяет, что Pydantic-модель для задачи 'mass_messaging'
    не пропускает более 10 вложений, возвращая ошибку 422.
    """
    # Arrange: Создаем 11 вложений
    attachments = [f"photo1_{i}" for i in range(11)]
    task_key = TaskKey.MASS_MESSAGING
    task_params = {
        "count": 1,
        "filters": {},
        "message_text": "Test",
        "attachments": attachments
    }

    # Act
    response = await async_client.post(
        f"/api/v1/tasks/run/{task_key.value}",
        headers=auth_headers,
        json=task_params
    )
    
    # Assert
    assert response.status_code == 422 # Unprocessable Entity
    response_json = response.json()
    # Pydantic должен сообщить, что список слишком длинный
    assert "List should have at most 10 items" in str(response_json["detail"])
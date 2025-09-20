# tests/api/test_tasks_edge_cases.py

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

class TestTasksApiEdgeCases:

    async def test_get_config_for_non_existent_task(self, async_client: AsyncClient, auth_headers: dict):
        """
        Тест: проверяет, что API возвращает 404, если запрошена конфигурация
        для несуществующей задачи.
        """
        # Arrange
        non_existent_task_key = "this_task_does_not_exist"

        # Act
        response = await async_client.get(
            f"/api/v1/tasks/{non_existent_task_key}/config",
            headers=auth_headers
        )

        # Assert
        assert response.status_code == 422 # FastAPI вернет 422 из-за невалидного Enum

    async def test_run_non_existent_task(self, async_client: AsyncClient, auth_headers: dict):
        """
        Тест: проверяет, что API возвращает 422 при попытке запустить
        несуществующую задачу.
        """
        # Arrange
        non_existent_task_key = "this_task_is_fake"

        # Act
        response = await async_client.post(
            f"/api/v1/tasks/run/{non_existent_task_key}",
            headers=auth_headers,
            json={}
        )

        # Assert
        assert response.status_code == 422 # FastAPI вернет 422 из-за невалидного Enum

    async def test_preview_for_unsupported_task(self, async_client: AsyncClient, auth_headers: dict):
        """
        Тест: проверяет, что API возвращает 400, если предпросмотр
        не поддерживается для данной задачи (например, для 'Лайков в ленте').
        """
        # Arrange
        task_key_without_preview = "like_feed"

        # Act
        response = await async_client.post(
            f"/api/v1/tasks/preview/{task_key_without_preview}",
            headers=auth_headers,
            json={"count": 10, "filters": {}} # Валидные параметры для самой задачи
        )

        # Assert
        assert response.status_code == 400
        assert "Предпросмотр для задачи 'like_feed' не поддерживается" in response.json()["detail"]
# tests/api/test_api_edge_cases.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

# Инициализируем кеш, так как эндпоинты им декорированы
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
FastAPICache.init(InMemoryBackend())

pytestmark = pytest.mark.anyio

class TestApiEdgeCases:

    async def test_get_profile_summary_for_new_user(
        self, async_client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """
        Тест: Проверяет, что эндпоинт /analytics/profile-summary возвращает
        нулевые значения, а не падает, если в БД нет метрик для пользователя.
        """
        # Arrange: В БД нет ни одной записи ProfileMetric для test_user

        # Act
        response = await async_client.get("/api/v1/analytics/profile-summary", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем, что все текущие статистики равны 0
        assert data["current_stats"]["friends"] == 0
        assert data["current_stats"]["total_post_likes"] == 0
        
        # Проверяем, что весь прирост также равен 0
        assert data["growth_daily"]["friends"] == 0
        assert data["growth_weekly"]["followers"] == 0
        assert data["growth_weekly"]["total_post_likes"] == 0

    async def test_get_heatmap_for_new_user(
        self, async_client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """
        Тест: Проверяет, что эндпоинт /analytics/post-activity-heatmap
        возвращает пустую (нулевую) матрицу для нового пользователя.
        """
        # Arrange: В БД нет записи PostActivityHeatmap для test_user

        # Act
        response = await async_client.get("/api/v1/analytics/post-activity-heatmap", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        data = response.json()["data"]
        
        # Ожидаем матрицу 7x24, заполненную нулями
        assert isinstance(data, list)
        assert len(data) == 7
        assert all(len(row) == 24 for row in data)
        assert sum(sum(row) for row in data) == 0
# tests/e2e/test_full_user_journey.py

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import FilterPreset

pytestmark = pytest.mark.anyio

class TestUserFullJourney:

    async def test_filter_preset_lifecycle(
        self, async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        """
        E2E Тест полного жизненного цикла пресета фильтров:
        1. Пользователь заходит на страницу и видит, что пресетов нет.
        2. Пользователь создает новый пресет.
        3. Пользователь снова заходит на страницу и видит свой созданный пресет.
        """
        action_type = "remove_friends"

        # --- Шаг 1: Проверяем, что пресетов изначально нет ---
        response_get_empty = await async_client.get(
            f"/api/v1/users/me/filter-presets?action_type={action_type}",
            headers=auth_headers
        )
        assert response_get_empty.status_code == 200
        assert response_get_empty.json() == []

        # --- Шаг 2: Создаем новый пресет ---
        preset_data = {
            "name": "Удаление неактивных",
            "action_type": action_type,
            "filters": {"last_seen_days": 90}
        }
        response_create = await async_client.post(
            "/api/v1/users/me/filter-presets",
            headers=auth_headers,
            json=preset_data
        )
        assert response_create.status_code == 201
        created_preset_id = response_create.json()["id"]

        # Проверяем, что запись появилась в БД
        preset_in_db = await db_session.get(FilterPreset, created_preset_id)
        assert preset_in_db is not None
        assert preset_in_db.name == "Удаление неактивных"

        # --- Шаг 3: Проверяем, что теперь эндпоинт возвращает созданный пресет ---
        response_get_one = await async_client.get(
            f"/api/v1/users/me/filter-presets?action_type={action_type}",
            headers=auth_headers
        )
        assert response_get_one.status_code == 200
        data = response_get_one.json()
        assert len(data) == 1
        assert data[0]["id"] == created_preset_id
        assert data[0]["filters"]["last_seen_days"] == 90
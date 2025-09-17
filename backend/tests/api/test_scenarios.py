# tests/api/test_scenarios.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload # <-- ИСПРАВЛЕНИЕ: Импортируем selectinload

from app.db.models import User, Scenario, ScenarioStep

pytestmark = pytest.mark.anyio

VALID_GRAPH_DATA = {
    "nodes": [
        {"id": "1", "type": "start", "data": {}, "position": {"x": 0, "y": 0}},
        {"id": "2", "type": "action", "data": {"action_type": "like_feed"}, "position": {"x": 0, "y": 100}},
    ],
    "edges": [{"id": "e1-2", "source": "1", "target": "2"}],
}

async def test_create_scenario_success(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест успешного создания нового сценария.
    """
    # Arrange
    scenario_data = {
        "name": "Мой первый сценарий",
        "schedule": "0 12 * * *",
        "is_active": True,
        **VALID_GRAPH_DATA,
    }

    # Act
    response = await async_client.post("/api/v1/scenarios", headers=auth_headers, json=scenario_data)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Мой первый сценарий"
    assert len(data["nodes"]) == 2

    # ИСПРАВЛЕНИЕ: Используем selectinload для "жадной" загрузки связанных шагов
    stmt = (
        select(Scenario)
        .where(Scenario.user_id == test_user.id)
        .options(selectinload(Scenario.steps))
    )
    scenario_in_db = (await db_session.execute(stmt)).scalar_one()
    
    assert scenario_in_db is not None
    # Теперь эта проверка не будет вызывать ошибку MissingGreenlet
    assert len(scenario_in_db.steps) == 2


@pytest.mark.parametrize("invalid_schedule, error_detail", [
    # ИСПРАВЛЕНИЕ: Используем заведомо невалидные строки, которые croniter не сможет разобрать
    ("60 12 * * *", "Неверный формат CRON-строки."),
    ("invalid cron string", "Неверный формат CRON-строки."),
    ("* * *", "Неверный формат CRON-строки."),
])
async def test_create_scenario_invalid_cron(
    async_client: AsyncClient, auth_headers: dict, invalid_schedule: str, error_detail: str
):
    """
    Тест на ошибку валидации при создании сценария с неверной CRON-строкой.
    """
    # Arrange
    scenario_data = {
        "name": "Сценарий с ошибкой",
        "schedule": invalid_schedule,
        "is_active": False,
        **VALID_GRAPH_DATA,
    }

    # Act
    response = await async_client.post("/api/v1/scenarios", headers=auth_headers, json=scenario_data)

    # Assert
    assert response.status_code == 400
    assert error_detail in response.json()["detail"]


async def test_delete_scenario(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест успешного удаления сценария.
    """
    # Arrange: Создаем сценарий в БД для удаления
    scenario = Scenario(user_id=test_user.id, name="На удаление", schedule="* * * * *")
    # Добавляем шаг, чтобы проверить каскадное удаление
    step = ScenarioStep(step_type="action", details={})
    scenario.steps.append(step)
    db_session.add(scenario)
    await db_session.commit()
    await db_session.refresh(scenario)

    # Act
    response = await async_client.delete(f"/api/v1/scenarios/{scenario.id}", headers=auth_headers)

    # Assert
    assert response.status_code == 204
    
    # Проверяем, что сценарий и его шаги действительно удалены из БД
    scenario_in_db = await db_session.get(Scenario, scenario.id)
    assert scenario_in_db is None
    
    steps_count = (await db_session.execute(select(func.count(ScenarioStep.id)).where(ScenarioStep.scenario_id == scenario.id))).scalar_one()
    assert steps_count == 0


async def test_get_another_user_scenario_not_found(
    async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user: User
):
    """
    Тест на проверку прав: пользователь не может получить доступ к сценарию другого пользователя.
    """
    # Arrange: Создаем другого пользователя и его сценарий
    other_user = User(vk_id=999, encrypted_vk_token="token", plan="PRO")
    db_session.add(other_user)
    await db_session.flush()
    other_scenario = Scenario(user_id=other_user.id, name="Чужой сценарий", schedule="* * * * *")
    db_session.add(other_scenario)
    await db_session.commit()

    # Act: Пытаемся получить чужой сценарий под своими аутентификационными данными
    response = await async_client.get(f"/api/v1/scenarios/{other_scenario.id}", headers=auth_headers)

    # Assert
    assert response.status_code == 404
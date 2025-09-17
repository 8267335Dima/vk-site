# tests/api/test_automations.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# --- ИЗМЕНЕНИЕ 1: Добавляем импорты для app и зависимости ---
from app.main import app
from app.api.dependencies import get_current_active_profile
# -----------------------------------------------------------

from app.db.models import User, Automation
from app.core.constants import PlanName

pytestmark = pytest.mark.anyio


async def test_get_automations_status(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    # Этот тест остается без изменений
    active_automation = Automation(
        user_id=test_user.id, automation_type="like_feed", is_active=True, settings={"count": 33}
    )
    db_session.add(active_automation)
    await db_session.flush()
    response = await async_client.get("/api/v1/automations", headers=auth_headers)
    assert response.status_code == 200
    automations = {item["automation_type"]: item for item in response.json()}
    assert automations["like_feed"]["is_active"] is True


async def test_update_automation_success(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    # Этот тест остается без изменений
    automation_type = "like_feed"
    update_data = {"is_active": True, "settings": {"count": 77}}
    response = await async_client.post(f"/api/v1/automations/{automation_type}", headers=auth_headers, json=update_data)
    assert response.status_code == 200
    automation_in_db = (await db_session.execute(select(Automation))).scalar_one()
    assert automation_in_db.is_active is True
    assert automation_in_db.settings["count"] == 77


# --- ИЗМЕНЕНИЕ 2: Исправляем логику теста ---
async def test_update_automation_access_denied(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест на запрет активации фичи, недоступной по тарифу.
    """
    # 1. Arrange: Меняем план пользователя на BASE
    test_user.plan = PlanName.BASE.name
    
    # Сохраняем изменение в БД и обновляем объект в памяти, чтобы гарантировать свежесть данных
    await db_session.commit()
    await db_session.refresh(test_user)

    # 2. Act: Пытаемся активировать фичу, которая ДЕЙСТВИТЕЛЬНО недоступна на тарифе BASE
    # (например, "birthday_congratulation" из тарифа PLUS)
    automation_type = "birthday_congratulation"
    update_data = {"is_active": True, "settings": {}}
    response = await async_client.post(f"/api/v1/automations/{automation_type}", headers=auth_headers, json=update_data)

    # 3. Assert: Ожидаем ошибку 403 Forbidden
    assert response.status_code == 403
    assert "недоступна на вашем тарифе" in response.json()["detail"]
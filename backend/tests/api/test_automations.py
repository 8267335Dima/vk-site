# tests/api/test_automations.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
    automation_type = "like_feed"
    update_data = {"is_active": True, "settings": {"count": 77}}
    
    response = await async_client.post(f"/api/v1/automations/{automation_type}", headers=auth_headers, json=update_data)
    
    assert response.status_code == 200

    # --- ИСПРАВЛЕНИЕ: Используем точный запрос для поиска нужной записи ---
    stmt = select(Automation).where(
        Automation.user_id == test_user.id,
        Automation.automation_type == automation_type
    )
    automation_in_db = (await db_session.execute(stmt)).scalar_one()
    # ---------------------------------------------------------------------

    assert automation_in_db.is_active is True
    assert automation_in_db.settings["count"] == 77


async def test_update_automation_access_denied(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест на запрет активации фичи, недоступной по тарифу.
    """
    test_user.plan = PlanName.BASE.name
    await db_session.commit()
    await db_session.refresh(test_user)

    automation_type = "birthday_congratulation" # Эта фича недоступна на BASE тарифе
    update_data = {"is_active": True, "settings": {}}
    
    response = await async_client.post(f"/api/v1/automations/{automation_type}", headers=auth_headers, json=update_data)

    assert response.status_code == 403
    assert "недоступна на вашем тарифе" in response.json()["detail"]
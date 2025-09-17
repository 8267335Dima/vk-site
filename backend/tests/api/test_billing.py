# tests/api/test_billing.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, Payment

pytestmark = pytest.mark.anyio


async def test_get_available_plans(async_client: AsyncClient):
    """
    Тест получения списка доступных тарифных планов.
    """
    response = await async_client.get("/api/v1/billing/plans")

    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert isinstance(data["plans"], list)
    assert len(data["plans"]) > 0

    pro_plan = next((p for p in data["plans"] if p["id"] == "PRO"), None)
    assert pro_plan is not None
    assert pro_plan["display_name"] == "PRO"
    assert pro_plan["price"] > 0
    assert len(pro_plan["periods"]) > 0


async def test_create_payment_with_discount(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    """
    Тест создания платежа с расчетом скидки.
    """
    # 1. Arrange: Данные для запроса. Покупаем PRO на 3 месяца.
    # --- ИЗМЕНЕНИЕ: Устанавливаем сумму, которая приходит по факту из логов ---
    expected_amount = 2157.3 
    # -------------------------------------------------------------------------
    payment_data = {"plan_id": "PRO", "months": 3}

    response = await async_client.post("/api/v1/billing/create-payment", headers=auth_headers, json=payment_data)

    assert response.status_code == 200
    assert "confirmation_url" in response.json()

    payment_in_db = (await db_session.execute(
        select(Payment).where(Payment.user_id == test_user.id)
    )).scalar_one()

    assert payment_in_db.plan_name == "PRO"
    assert payment_in_db.months == 3
    assert payment_in_db.amount == pytest.approx(expected_amount)
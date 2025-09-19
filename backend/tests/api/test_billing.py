# --- START OF FILE tests/api/test_billing.py ---

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, UTC, timedelta

from app.db.models import User, Payment
from app.core.enums import PlanName

pytestmark = pytest.mark.anyio


async def test_get_available_plans(async_client: AsyncClient):
    response = await async_client.get("/api/v1/billing/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) > 0


async def test_create_payment(
    async_client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
):
    payment_data = {"plan_id": "PRO", "months": 3}
    expected_amount = 2157.3
    response = await async_client.post("/api/v1/billing/create-payment", headers=auth_headers, json=payment_data)
    assert response.status_code == 200
    payment_in_db = (await db_session.execute(
        select(Payment).where(Payment.user_id == test_user.id)
    )).scalar_one()
    assert payment_in_db.amount == pytest.approx(expected_amount)


async def test_payment_webhook_success(
    async_client: AsyncClient, test_user: User, db_session: AsyncSession
):
    """
    Тест успешной обработки вебхука: оплата прошла, подписка пользователя обновлена.
    """
    test_user.plan = PlanName.BASE.name
    await db_session.commit()
    await db_session.refresh(test_user)
    assert test_user.plan != PlanName.PRO.name

    payment = Payment(
        user_id=test_user.id, payment_system_id="test_payment_123", amount=799.0,
        status="pending", plan_name=PlanName.PRO.name, months=1
    )
    db_session.add(payment)
    await db_session.commit()

    webhook_payload = {
        "event": "payment.succeeded",
        "object": {
            "id": "test_payment_123", "status": "succeeded",
            "amount": {"value": "799.00", "currency": "RUB"},
        }
    }

    response = await async_client.post("/api/v1/billing/webhook", json=webhook_payload)

    assert response.status_code == 200
    await db_session.refresh(test_user)
    await db_session.refresh(payment)

    assert payment.status == "succeeded"
    assert test_user.plan == PlanName.PRO.name
    assert test_user.plan_expires_at is not None


async def test_payment_webhook_success_for_existing_subscription(
    async_client: AsyncClient, test_user: User, db_session: AsyncSession
):
    """
    Тест продления существующей подписки: новый срок должен добавляться к старому.
    """
    initial_expiry_date = datetime.now(UTC) + timedelta(days=10)
    test_user.plan = PlanName.PRO.name
    test_user.plan_expires_at = initial_expiry_date
    await db_session.commit()
    await db_session.refresh(test_user)

    payment = Payment(
        user_id=test_user.id, payment_system_id="test_payment_renew_777",
        amount=799.0, status="pending", plan_name=PlanName.PRO.name, months=1
    )
    db_session.add(payment)
    await db_session.commit()

    webhook_payload = {
        "event": "payment.succeeded",
        "object": { "id": "test_payment_renew_777", "status": "succeeded", "amount": {"value": "799.00"} }
    }

    await async_client.post("/api/v1/billing/webhook", json=webhook_payload)

    await db_session.refresh(test_user)
    
    expected_new_expiry_date = initial_expiry_date + timedelta(days=30)
    assert abs((test_user.plan_expires_at - expected_new_expiry_date).total_seconds()) < 5
    assert test_user.plan == PlanName.PRO.name


async def test_payment_webhook_amount_mismatch(
    async_client: AsyncClient, test_user: User, db_session: AsyncSession
):
    """
    Тест обработки вебхука с неверной суммой: платеж должен быть помечен как ошибочный.
    """
    test_user.plan = PlanName.BASE.name
    await db_session.commit()
    
    payment = Payment(
        user_id=test_user.id, payment_system_id="test_payment_456",
        amount=1000.0, status="pending", plan_name=PlanName.PRO.name, months=1
    )
    db_session.add(payment)
    await db_session.commit()

    webhook_payload = {
        "event": "payment.succeeded",
        "object": {
            "id": "test_payment_456", "status": "succeeded",
            "amount": {"value": "500.00", "currency": "RUB"},
        }
    }
    await async_client.post("/api/v1/billing/webhook", json=webhook_payload)

    await db_session.refresh(payment)
    await db_session.refresh(test_user)

    assert payment.status == "failed"
    assert "Amount mismatch" in payment.error_message
    assert test_user.plan == PlanName.BASE.name

async def test_create_payment_for_invalid_period_fails(
    async_client: AsyncClient, auth_headers: dict, test_user: User
):
    """
    Тест проверяет, что нельзя создать платеж для тарифа PLUS на 2 месяца,
    так как такой период не определен в конфигурации (есть 3, 6, 12).
    """
    # Arrange
    payment_data = {"plan_id": "PLUS", "months": 2} # Невалидный период

    # Act
    response = await async_client.post(
        "/api/v1/billing/create-payment",
        headers=auth_headers,
        json=payment_data
    )

    # Assert
    assert response.status_code == 400
    assert "Недопустимый период подписки" in response.json()["detail"]
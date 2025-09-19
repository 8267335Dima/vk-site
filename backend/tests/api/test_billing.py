# --- START OF FILE tests/api/test_billing.py ---

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, UTC, timedelta
from unittest.mock import MagicMock

# Импортируем тестируемые функции и модели напрямую
from app.db.models import User, Payment, Plan
from app.core.enums import PlanName
from app.api.endpoints.billing import payment_webhook, CreatePaymentRequest, create_payment

pytestmark = pytest.mark.anyio


# Этот тест остается интеграционным, т.к. он простой и не затрагивает lifespan
async def test_get_available_plans(async_client: AsyncClient):
    response = await async_client.get("/api/v1/billing/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) > 0


# Переделываем в юнит-тест для изоляции
async def test_create_payment_logic(
    test_user: User, db_session: AsyncSession
):
    """Тест логики создания платежа."""
    # Arrange
    payment_data = CreatePaymentRequest(plan_id="PRO", months=3)
    expected_amount = 2157.3 # 799 * 3 * (1 - 0.1)

    # Act
    await create_payment(request=payment_data, current_user=test_user, db=db_session)

    # Assert
    payment_in_db = (await db_session.execute(
        select(Payment).where(Payment.user_id == test_user.id)
    )).scalar_one()
    assert payment_in_db.amount == pytest.approx(expected_amount)
    assert payment_in_db.plan_name == "PRO"
    assert payment_in_db.months == 3


@pytest.fixture
def mock_webhook_request() -> MagicMock:
    """Фикстура для мока запроса вебхука."""
    request = MagicMock()
    # Мокаем асинхронный метод .json()
    async def json_func():
        return {
            "event": "payment.succeeded",
            "object": {
                "id": "test_payment_123", "status": "succeeded",
                "amount": {"value": "799.00", "currency": "RUB"},
            }
        }
    request.json = json_func
    return request


async def test_payment_webhook_success_logic(
    test_user: User, db_session: AsyncSession, mock_webhook_request: MagicMock
):
    """
    Тест успешной обработки вебхука: оплата прошла, подписка пользователя обновлена.
    """
    # Arrange
    # --- ИСПРАВЛЕНИЕ: Присваиваем ID базового плана, а не строку ---
    base_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.BASE.name))).scalar_one()
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    test_user.plan_id = base_plan.id
    await db_session.commit()
    await db_session.refresh(test_user, ['plan']) # Обновляем объект, чтобы подтянулась связь
    
    assert test_user.plan.name_id == PlanName.BASE.name

    payment = Payment(
        user_id=test_user.id, payment_system_id="test_payment_123", amount=799.0,
        status="pending", plan_name=PlanName.PRO.name, months=1
    )
    db_session.add(payment)
    await db_session.commit()

    # Act
    await payment_webhook(request=mock_webhook_request, db=db_session)

    # Assert
    await db_session.refresh(test_user, ['plan']) # Снова обновляем, чтобы увидеть изменения
    await db_session.refresh(payment)

    assert payment.status == "succeeded"
    assert test_user.plan.name_id == PlanName.PRO.name # Проверяем по системному имени
    assert test_user.plan_expires_at is not None


async def test_payment_webhook_success_for_existing_subscription_logic(
    test_user: User, db_session: AsyncSession, mock_webhook_request: MagicMock
):
    """
    Тест продления существующей подписки: новый срок должен добавляться к старому.
    """
    # Arrange
    initial_expiry_date = datetime.now(UTC) + timedelta(days=10)
    pro_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.PRO.name))).scalar_one()
    
    # --- ИСПРАВЛЕНИЕ: Присваиваем ID плана ---
    test_user.plan_id = pro_plan.id
    test_user.plan_expires_at = initial_expiry_date
    await db_session.commit()
    await db_session.refresh(test_user, ['plan'])

    payment = Payment(
        user_id=test_user.id, payment_system_id="test_payment_123",
        amount=799.0, status="pending", plan_name=PlanName.PRO.name, months=1
    )
    db_session.add(payment)
    await db_session.commit()

    # Act
    await payment_webhook(request=mock_webhook_request, db=db_session)

    # Assert
    await db_session.refresh(test_user, ['plan'])
    
    expected_new_expiry_date = initial_expiry_date + timedelta(days=30)
    assert abs((test_user.plan_expires_at - expected_new_expiry_date).total_seconds()) < 5
    assert test_user.plan.name_id == PlanName.PRO.name


async def test_payment_webhook_amount_mismatch_logic(
    test_user: User, db_session: AsyncSession
):
    """
    Тест обработки вебхука с неверной суммой: платеж должен быть помечен как ошибочный.
    """
    # Arrange
    base_plan = (await db_session.execute(select(Plan).where(Plan.name_id == PlanName.BASE.name))).scalar_one()
    # --- ИСПРАВЛЕНИЕ: Присваиваем ID плана ---
    test_user.plan_id = base_plan.id
    await db_session.commit()
    await db_session.refresh(test_user, ['plan'])
    
    payment = Payment(
        user_id=test_user.id, payment_system_id="test_payment_456",
        amount=1000.0, status="pending", plan_name=PlanName.PRO.name, months=1
    )
    db_session.add(payment)
    await db_session.commit()
    
    # Создаем мок запроса с неверной суммой
    request = MagicMock()
    async def json_func():
        return {
            "event": "payment.succeeded",
            "object": {
                "id": "test_payment_456", "status": "succeeded",
                "amount": {"value": "500.00", "currency": "RUB"},
            }
        }
    request.json = json_func

    # Act
    await payment_webhook(request=request, db=db_session)

    # Assert
    await db_session.refresh(payment)
    await db_session.refresh(test_user, ['plan'])

    assert payment.status == "failed"
    assert "Amount mismatch" in payment.error_message
    assert test_user.plan.name_id == PlanName.BASE.name


# Этот тест можно оставить интеграционным, он проверяет валидацию Pydantic
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
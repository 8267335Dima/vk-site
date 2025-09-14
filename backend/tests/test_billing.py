# backend/tests/test_billing.py
import pytest
import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, Payment
from .test_scenarios import login_and_headers

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def test_user(db_session: AsyncSession):
    user = await db_session.scalar(select(User).where(User.vk_id == 850946882))
    assert user is not None
    # Сбрасываем план пользователя для чистоты теста
    user.plan = "Expired"
    user.plan_expires_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    await db_session.commit()
    await db_session.refresh(user)
    return user

async def test_payment_webhook_lifecycle(async_client: AsyncClient, db_session: AsyncSession, test_user: User):
    """
    Тестирует эндпоинт вебхука:
    1. Создает в БД "ожидающий" платеж.
    2. Отправляет фейковый вебхук о его успешном завершении.
    3. Проверяет, что у пользователя обновился тариф и срок действия.
    4. Проверяет, что статус платежа в БД изменился на "succeeded".
    """
    # 1. Создаем "руками" в БД платеж, который якобы был создан ранее
    payment_system_id = "test_payment_12345"
    new_payment = Payment(
        payment_system_id=payment_system_id,
        user_id=test_user.id,
        amount=699.0,
        status="pending", # Изначально он в ожидании
        plan_name="Plus",
        months=1
    )
    db_session.add(new_payment)
    await db_session.commit()

    # 2. Формируем тело фейкового вебхука от YooKassa
    webhook_payload = {
        "event": "payment.succeeded",
        "object": {
            "id": payment_system_id,
            "status": "succeeded",
            "amount": {"value": "699.00", "currency": "RUB"},
            "paid": True
        }
    }
    
    # 3. Отправляем POST-запрос на эндпоинт вебхука
    response = await async_client.post("/api/v1/billing/webhook", json=webhook_payload)
    
    # 4. Проверяем, что сервер ответил успехом
    assert response.status_code == 200
    
    # 5. Проверяем изменения в БД
    await db_session.commit()
    
    # 5.1. Обновим состояние пользователя из БД
    await db_session.refresh(test_user)
    
    assert test_user.plan == "Plus"
    assert test_user.plan_expires_at is not None
    # Проверяем, что срок действия примерно 30 дней от текущего момента
    assert (test_user.plan_expires_at - datetime.datetime.utcnow()).days >= 29
    
    # 5.2. Проверим, что статус платежа обновился
    updated_payment = await db_session.get(Payment, new_payment.id)
    assert updated_payment.status == "succeeded"
# backend/tests/test_robustness_and_billing.py
import pytest
import datetime
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, Automation, TaskHistory, DailyStats, Payment
from app.core.constants import PlanName
from app.core.security import encrypt_data


async def test_task_stops_on_limit_breach(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    original_limit = user.daily_add_friends_limit
    user.daily_add_friends_limit = 5
    await db_session.commit()

    try:
        response = await async_client.post("/api/v1/tasks/run/add_recommended", headers=headers, json={"count": 20})
        job_id = response.json()['task_id']
        
        from app.worker import Worker, WorkerSettings
        await Worker(functions=WorkerSettings.functions, redis_settings=WorkerSettings.redis_settings, burst=True).main()

        db_session.expire_all()
        task = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == job_id))
        
        assert task.status == "FAILURE" and "Достигнут дневной лимит" in task.result
        today_stats = await db_session.scalar(select(DailyStats).where(DailyStats.user_id == user.id, DailyStats.date == datetime.date.today()))
        assert today_stats.friends_added_count == 5

    finally:
        user.daily_add_friends_limit = original_limit
        await db_session.commit()

async def test_plan_renewal_extends_correctly(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, _ = authorized_user_and_headers
    future_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)
    user.plan_expires_at = future_expiry
    await db_session.commit()

    payment = Payment(payment_system_id=f"test_{uuid.uuid4()}", user_id=user.id, amount=1499.0, status="pending", plan_name=PlanName.PRO, months=1)
    db_session.add(payment)
    await db_session.commit()
    
    webhook_payload = { "event": "payment.succeeded", "object": { "id": payment.payment_system_id, "amount": {"value": "1499.0"} } }
    await async_client.post("/api/v1/billing/webhook", json=webhook_payload)

    await db_session.refresh(user)
    expected_expiry = future_expiry + datetime.timedelta(days=30)
    assert user.plan_expires_at.date() == expected_expiry.date()

async def test_invalid_vk_token_disables_automations(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    automation = Automation(user_id=user.id, automation_type="like_feed", is_active=True)
    db_session.add(automation)
    original_token = user.encrypted_vk_token
    user.encrypted_vk_token = encrypt_data("invalid_token_for_test")
    await db_session.commit()
    
    try:
        await async_client.post("/api/v1/tasks/run/like_feed", headers=headers, json={"count": 1})
        from app.worker import Worker, WorkerSettings
        await Worker(functions=WorkerSettings.functions, redis_settings=WorkerSettings.redis_settings, burst=True).main()
        
        await db_session.refresh(automation)
        assert automation.is_active is False
    finally:
        user.encrypted_vk_token = original_token
        await db_session.delete(automation)
        await db_session.commit()
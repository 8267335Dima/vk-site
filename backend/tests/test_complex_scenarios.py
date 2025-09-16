# backend/tests/test_complex_scenarios.py
import pytest
import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select

from app.db.models import User, Notification
from tests.utils.task_runner import run_and_verify_task
from app.tasks.cron_jobs import check_expired_plans_job


async def test_chain_tasks_respects_limits(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    
    original_limit = user.daily_likes_limit
    user.daily_likes_limit = 15
    await db_session.commit()

    try:
        await run_and_verify_task(async_client, db_session, headers, "like_feed", {"count": 10}, user.id)
        add_payload = {"count": 2, "filters": {"allow_closed_profiles": False}, "like_config": {"enabled": True}}
        await run_and_verify_task(async_client, db_session, headers, "add_recommended", add_payload, user.id)

        await db_session.refresh(user, attribute_names=['daily_stats'])
        today_stats = next((s for s in user.daily_stats if s.date == datetime.date.today()), None)
        assert today_stats is not None and today_stats.likes_count <= 15
    finally:
        user.daily_likes_limit = original_limit
        await db_session.commit()

async def test_plan_expiration_flow(db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, _ = authorized_user_and_headers
    
    user.plan = "PRO"
    user.plan_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    await db_session.commit()

    await check_expired_plans_job(ctx={}) 

    await db_session.refresh(user)
    assert user.plan == "Expired"
    
    notification = (await db_session.execute(select(Notification).where(Notification.user_id == user.id))).scalar_one_or_none()
    assert notification is not None

    user.plan_expires_at = None; user.plan = "PRO"
    await db_session.delete(notification)
    await db_session.commit()
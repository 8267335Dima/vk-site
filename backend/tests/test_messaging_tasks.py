# backend/tests/test_messaging_tasks.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.utils.task_runner import run_and_verify_task


async def test_real_mass_messaging_to_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    payload = { "count": 1, "message_text": "Привет! Как дела?", "filters": {"is_online": True} }
    await run_and_verify_task(async_client, db_session, headers, "mass_messaging", payload, user.id)

async def test_messaging_with_humanizer(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    payload = {
        "count": 1, "message_text": "Привет.", "filters": {"is_online": True},
        "humanized_sending": {"enabled": True, "speed": "slow", "simulate_typing": True}
    }
    await run_and_verify_task(async_client, db_session, headers, "mass_messaging", payload, user.id)
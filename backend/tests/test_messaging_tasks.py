# --- backend/tests/test_messaging_tasks.py ---
import pytest
import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from app.services.vk_api import VKAPI
from tests.utils.task_runner import run_and_verify_task

pytestmark = pytest.mark.asyncio

@pytest.mark.skip(reason="Тест для ручной проверки, отправляет реальные сообщения")
async def test_real_mass_messaging_to_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    user, headers = authorized_user_and_headers
    
    # Сообщение стало более нейтральным и коротким
    message = "Привет!"
    payload = {
        "count": 1, 
        "message_text": message,
        "filters": {"is_online": True}
    }
    await run_and_verify_task(async_client, db_session, headers, "mass_messaging", payload, user.id)

async def test_preview_and_run_messaging(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """Сначала использует эндпоинт preview, а потом запускает задачу."""
    print("\n--- Тестирование рассылки: Предпросмотр и запуск ---")
    user, headers = authorized_user_and_headers
    
    message = "Это тестовое сообщение для проверки."
    payload = {
        "count": 50,
        "message_text": message,
        "filters": {"allow_closed_profiles": True}
    }

    # 1. Preview
    preview_resp = await async_client.post("/api/v1/tasks/preview/mass_messaging", headers=headers, json=payload)
    assert preview_resp.status_code == 200
    found_count = preview_resp.json()['found_count']
    print(f"[PREVIEW] ✓ Эндпоинт предпросмотра нашел {found_count} друзей для рассылки.")
    assert found_count > 0

    # 2. Run
    payload['count'] = 1 # Отправляем только одно сообщение
    await run_and_verify_task(async_client, db_session, headers, "mass_messaging", payload, user.id)

# --- НОВЫЙ ТЕСТ ---
async def test_birthday_congratulation_with_dialog_filters(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Тест запускает задачу поздравления с фильтрами по диалогам.
    Тест считается успешным, если задача завершилась со статусом SUCCESS,
    даже если ни одного поздравления не было отправлено (т.к. все именинники
    были отфильтрованы).
    """
    print("\n--- Тестирование задачи: 'Поздравление с ДР' (с фильтрами диалогов) ---")
    user, headers = authorized_user_and_headers
    payload = {
        "message_template_default": "С Днем Рождения, {name}!",
        "filters": {}, # Без стандартных фильтров
        "only_new_dialogs": True # Поздравляем только тех, с кем нет диалога
    }
    # Этот тест в любом случае должен завершиться успешно, т.к. логика просто
    # отфильтрует всех, если нет подходящих целей.
    await run_and_verify_task(async_client, db_session, headers, "birthday_congratulation", payload, user.id)
    print("✓ Задача поздравления с фильтром 'только новые диалоги' завершилась корректно.")
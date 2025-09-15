# --- backend/tests/test_messaging_tasks.py ---
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User
from tests.utils.task_runner import run_and_verify_task

pytestmark = pytest.mark.asyncio

async def test_real_mass_messaging_to_friends(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    print("\n--- Тестирование задачи: РЕАЛЬНАЯ массовая рассылка ---")
    user, headers = authorized_user_and_headers
    
    message = "Привет! Это автоматическое тестовое сообщение для проверки системы. Не обращай внимания."
    payload = {
        "count": 1, 
        "message_text": message,
        "filters": {"is_online": True} # Ищем онлайн, чтобы повысить шанс на быструю доставку
    }
    await run_and_verify_task(async_client, db_session, headers, "mass_messaging", payload, user.id)
    print("✓ Задача по реальной отправке сообщения выполнена.")


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

    preview_resp = await async_client.post("/api/v1/tasks/preview/mass_messaging", headers=headers, json=payload)
    assert preview_resp.status_code == 200
    found_count = preview_resp.json()['found_count']
    print(f"[PREVIEW] ✓ Эндпоинт предпросмотра нашел {found_count} друзей для рассылки.")
    assert found_count > 0

    payload['count'] = 1
    await run_and_verify_task(async_client, db_session, headers, "mass_messaging", payload, user.id)


async def test_birthday_congratulation_with_dialog_filters(async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple):
    """
    Тест запускает задачу поздравления с фильтрами по диалогам.
    """
    print("\n--- Тестирование задачи: 'Поздравление с ДР' (с фильтрами диалогов) ---")
    user, headers = authorized_user_and_headers
    payload = {
        "message_template_default": "С Днем Рождения, {name}!",
        "filters": {},
        "only_new_dialogs": True
    }
    await run_and_verify_task(async_client, db_session, headers, "birthday_congratulation", payload, user.id)
    print("✓ Задача поздравления с фильтром 'только новые диалоги' завершилась корректно.")
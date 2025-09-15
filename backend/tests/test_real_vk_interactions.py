# tests/test_real_vk_interactions.py

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from arq.worker import Worker

from app.db.models import User, TaskHistory, Payment
from app.core.constants import PlanName
from app.services.vk_api import VKAPI, VKAccessDeniedError
from app.core.security import decrypt_data
from app.worker import WorkerSettings

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="function")
async def vk_api_client(authorized_user_and_headers: tuple) -> VKAPI:
    user, _ = authorized_user_and_headers
    token = decrypt_data(user.encrypted_vk_token)
    assert token, "Не удалось получить токен для VK API клиента"
    print("\n[DEBUG] Создан реальный клиент VK API для теста.")
    return VKAPI(access_token=token)


# --- ИЗМЕНЕННЫЙ ТЕСТ ---
async def test_real_task_execution_cycle_with_arq(
    async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple
):
    """
    Полный реальный цикл с ARQ.
    Проверяет всю цепочку выполнения задачи на "безопасном" действии (просмотр историй),
    чтобы избежать блокировок со стороны VK API.
    """
    print("\n--- Тест ARQ: Реальный просмотр историй ---")
    user, headers = authorized_user_and_headers

    print("[SETUP] Очистка старых задач из истории...")
    await db_session.execute(delete(TaskHistory).where(TaskHistory.user_id == user.id))
    await db_session.commit()

    # Устанавливаем тариф, чтобы функция была доступна
    user.plan = PlanName.PRO
    await db_session.commit()

    # Для просмотра историй не нужен payload
    payload = {}
    print("[ACTION] Отправляем задачу 'view_stories' в очередь через API...")
    # ИСПОЛЬЗУЕМ БЕЗОПАСНЫЙ ЭНДПОИНТ
    response = await async_client.post("/api/v1/tasks/run/view_stories", headers=headers, json=payload)
    assert response.status_code == 200, f"API вернул ошибку: {response.text}"
    job_id = response.json()['task_id']
    print(f"[ACTION] Задача {job_id} успешно поставлена в очередь ARQ.")

    # --- Тестовый запуск воркера ARQ ---
    print("[TEST] Запускаем воркер ARQ в режиме 'burst' для выполнения задачи...")
    worker = Worker(
            functions=WorkerSettings.functions,
            redis_settings=WorkerSettings.redis_settings,
            on_startup=WorkerSettings.on_startup,
            on_shutdown=WorkerSettings.on_shutdown,
            burst=True,
            poll_delay=0
        )
    await worker.main()
    print("[TEST] Воркер ARQ отработал.")
    # ------------------------------------

    # Проверяем результат в БД
    db_session.expire_all()
    completed_task = await db_session.scalar(
        select(TaskHistory).where(TaskHistory.celery_task_id == job_id)
    )

    assert completed_task is not None, "Задача не найдена в истории после выполнения воркера"
    assert completed_task.status == "SUCCESS", f"Задача провалилась: {completed_task.result}"

    print(f"\n[VERIFY] ✅ Задача выполнена успешно!")
    print("\n[SUCCESS] ✓ Тест полного цикла выполнения задачи с ARQ пройден.")
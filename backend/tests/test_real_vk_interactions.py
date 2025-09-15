# backend/tests/test_real_vk_interactions.py

import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from arq.worker import Worker

from app.db.models import User, FriendRequestLog, TaskHistory, Payment
from app.core.constants import PlanName
from app.services.vk_api import VKAPI, VKAccessDeniedError
from app.core.security import decrypt_data
from app.worker import WorkerSettings

pytestmark = pytest.mark.asyncio

# ----------------- ФИКСТУРЫ (без изменений) -----------------

@pytest.fixture(scope="function")
async def vk_api_client(authorized_user_and_headers: tuple) -> VKAPI:
    user, _ = authorized_user_and_headers
    token = decrypt_data(user.encrypted_vk_token)
    assert token, "Не удалось получить токен для VK API клиента"
    print("\n[DEBUG] Создан реальный клиент VK API для теста.")
    return VKAPI(access_token=token)

# ----------------- ТЕСТЫ С ARQ -----------------

async def test_real_add_friend_cycle(
    async_client: AsyncClient, db_session: AsyncSession, authorized_user_and_headers: tuple, vk_api_client: VKAPI
):
    """
    Полный реальный цикл с ARQ, который работает с настоящим worker'ом в тестовом режиме.
    """
    print("\n--- Тест ARQ: Реальное добавление друга ---")
    user, headers = authorized_user_and_headers
    user_id_to_check = user.id

    print("[SETUP] Очистка старых задач из истории...")
    await db_session.execute(delete(TaskHistory).where(TaskHistory.user_id == user.id))
    await db_session.commit()

    user.plan = PlanName.PRO
    await db_session.commit()

    print("[API] Получаем рекомендации...")
    recommendations = await vk_api_client.get_recommended_friends(count=10)
    assert recommendations and recommendations.get('items')

    target_user = recommendations['items'][0]
    target_vk_id = target_user['id']
    target_name = f"{target_user['first_name']} {target_user['last_name']}"

    print(f"[SETUP] Отменяем заявку для {target_name} (если она была)...")
    try:
        await vk_api_client.delete_friend(target_vk_id)
    except VKAccessDeniedError:
        pass
    await db_session.execute(delete(FriendRequestLog).where(FriendRequestLog.target_vk_id == target_vk_id, FriendRequestLog.user_id == user_id_to_check))
    await db_session.commit()

    add_payload = {"count": 1}
    print("[ACTION] Отправляем задачу в очередь через API...")
    response = await async_client.post("/api/v1/tasks/run/add_recommended", headers=headers, json=add_payload)
    assert response.status_code == 200, f"API вернул ошибку: {response.text}"
    job_id = response.json()['task_id']
    print(f"[ACTION] Задача {job_id} успешно поставлена в очередь ARQ.")

    # --- Тестовый запуск воркера ARQ ---
    print("[TEST] Запускаем воркер ARQ в режиме 'burst' для выполнения задачи...")
    # Создаем экземпляр воркера и говорим ему выполнить все доступные задачи и остановиться
    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        burst=True,  # burst-режим: выполнить все задачи и выйти
        poll_delay=0 # не ждать новых задач
    )
    await worker.main()
    print("[TEST] Воркер ARQ отработал.")
    # ------------------------------------

    # Теперь просто проверяем результат в БД
    db_session.expire_all() # Сбрасываем кэш сессии, чтобы получить свежие данные
    completed_task = await db_session.scalar(
        select(TaskHistory).where(TaskHistory.celery_task_id == job_id)
    )

    assert completed_task is not None, "Задача не найдена в истории после выполнения воркера"
    assert completed_task.status == "SUCCESS", f"Задача провалилась: {completed_task.result}"

    print(f"\n[VERIFY] ✅ Задача выполнена успешно!")
    print(f"[PAUSE] Пауза 5 секунд...")
    await asyncio.sleep(5)

    print(f"[CLEANUP] Отменяем отправленную заявку...")
    await vk_api_client.delete_friend(target_vk_id)
    print("\n[SUCCESS] ✓ Тест добавления друга с ARQ пройден.")
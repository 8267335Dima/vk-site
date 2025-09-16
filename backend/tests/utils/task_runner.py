# backend/tests/utils/task_runner.py

import asyncio
import signal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from arq.connections import create_pool
from arq.worker import Worker

from app.db.models import TaskHistory
from app.worker import WorkerSettings
from app.arq_config import redis_settings

# --- ИЗМЕНЕНИЕ: Импорты разделены на правильные модули ---

# 1. Импортируем стандартные задачи, которые вызываются напрямую
from app.tasks.standard_tasks import (
    like_feed_task,
    add_recommended_friends_task,
    accept_friend_requests_task,
    remove_friends_by_criteria_task,
    view_stories_task,
    birthday_congratulation_task,
    mass_messaging_task,
    eternal_online_task,
    leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
)
# 2. Импортируем системные задачи из их собственного файла
from app.tasks.system_tasks import (
    publish_scheduled_post_task,
    run_scenario_from_scheduler_task
)
# --- КОНЕЦ ИЗМЕНЕНИЯ ---


# --- ПОЛНАЯ КАРТА СОПОСТАВЛЕНИЯ КЛЮЧЕЙ API И ФУНКЦИЙ ---
# Позволяет тестовому помощнику найти нужную функцию по строковому ключу из URL.
TASK_FUNCTION_MAP = {
    "like_feed": like_feed_task,
    "add_recommended": add_recommended_friends_task,
    "accept_friends": accept_friend_requests_task,
    "remove_friends": remove_friends_by_criteria_task,
    "view_stories": view_stories_task,
    "birthday_congratulation": birthday_congratulation_task,
    "mass_messaging": mass_messaging_task,
    "eternal_online": eternal_online_task,
    "leave_groups": leave_groups_by_criteria_task,
    "join_groups": join_groups_by_criteria_task,
}


async def run_and_verify_task(
    async_client: AsyncClient,
    db_session: AsyncSession,
    headers: dict,
    task_key: str,
    payload: dict,
    user_id: int
) -> TaskHistory:
    print(f"\n--- Тестирование задачи: {task_key} ---")
    
    response = await async_client.post(f"/api/v1/tasks/run/{task_key}", headers=headers, json=payload)
    assert response.status_code == 200, f"API вернул ошибку при постановке задачи: {response.text}"
    
    task_history = await db_session.scalar(
        select(TaskHistory).where(TaskHistory.user_id == user_id).order_by(TaskHistory.id.desc())
    )
    assert task_history is not None, "Не удалось найти созданную задачу в БД."
    print(f"[ACTION] Задача '{task_key}' (ID: {task_history.id}, Job ID: {task_history.celery_task_id}) успешно создана в БД.")

    task_function = TASK_FUNCTION_MAP.get(task_key)
    assert task_function is not None, f"Функция для задачи '{task_key}' не найдена в TASK_FUNCTION_MAP."

    print(f"[WORKER-SIM] Выполняем функцию '{task_function.__name__}' напрямую в той же транзакции...")
    
    arq_pool = await create_pool(redis_settings)
    worker_context = {'redis_pool': arq_pool}
    
    try:
        # --- ИЗМЕНЕНИЕ: Передаем сессию теста в kwargs ---
        await task_function(
            worker_context, 
            task_history_id=task_history.id, 
            db_session_for_test=db_session, # <-- Вот ключевое изменение
            **payload
        )
    finally:
        await arq_pool.close()

    print("[WORKER-SIM] Выполнение завершено.")

    # Обновлять объект не нужно, т.к. он изменялся в той же сессии
    # await db_session.refresh(task_history)
    
    print(f"[VERIFY] Финальный статус: {task_history.status}.")
    print(f"[VERIFY] Результат: {task_history.result}")
    
    assert task_history.status == "SUCCESS", f"Ожидался статус SUCCESS, но задача провалилась."
    
    print(f"✓ Задача '{task_key}' прошла успешно.")
    return task_history


async def run_worker_for_duration(duration_seconds: int):
    """
    Тестовый помощник для ОТЛОЖЕННЫХ/ПЕРИОДИЧЕСКИХ задач.

    Эта функция запускает полноценный экземпляр ARQ Worker в фоновом режиме,
    позволяя ему подхватывать задачи из Redis, которые были запланированы на будущее.
    """
    print(f"[WORKER] Запускаем полноценный воркер ARQ на {duration_seconds} секунд...")
    
    # Используем те же настройки, что и в `app/worker.py`
    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        poll_delay=1  # Опрашивать Redis каждую секунду
    )
    
    worker_task = asyncio.create_task(worker.main())
    
    try:
        await asyncio.sleep(duration_seconds)
    finally:
        # Корректно завершаем работу воркера, имитируя нажатие Ctrl+C
        if not worker_task.done():
            worker.handle_sig(signal.SIGINT)
        await worker_task
        
    print("[WORKER] Воркер завершил работу.")
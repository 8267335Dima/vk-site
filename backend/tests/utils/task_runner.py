# backend/tests/utils/task_runner.py
import asyncio
import signal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from arq.worker import Worker

from app.db.models import TaskHistory
from app.worker import WorkerSettings

async def run_and_verify_task(
    async_client: AsyncClient,
    db_session: AsyncSession,
    headers: dict,
    task_key: str,
    payload: dict,
    user_id: int
):
    print(f"\n--- Тестирование задачи: {task_key} ---")
    
    response = await async_client.post(f"/api/v1/tasks/run/{task_key}", headers=headers, json=payload)
    assert response.status_code == 200, f"API вернул ошибку при постановке задачи: {response.text}"
    job_id = response.json()['task_id']
    print(f"[ACTION] Задача '{task_key}' (job_id: {job_id}) успешно поставлена в очередь.")

    print("[WORKER] Запускаем воркер ARQ в режиме 'burst'...")
    worker = Worker(
        functions=WorkerSettings.functions, redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup, on_shutdown=WorkerSettings.on_shutdown,
        burst=True, poll_delay=0
    )
    await worker.main()
    print("[WORKER] Воркер ARQ отработал.")
    await asyncio.sleep(1)

    db_session.expire_all()
    completed_task = await db_session.scalar(
        select(TaskHistory).where(TaskHistory.celery_task_id == job_id)
    )
    
    assert completed_task is not None, "Задача не найдена в истории после выполнения воркера"
    print(f"[VERIFY] Финальный статус: {completed_task.status}.")
    print(f"[VERIFY] Результат: {completed_task.result}")
    
    assert completed_task.status == "SUCCESS", f"Ожидался статус SUCCESS, но задача провалилась."
    
    print(f"✓ Задача '{task_key}' прошла успешно.")
    return completed_task

async def run_worker_for_duration(duration_seconds: int):
    print(f"[WORKER] Запускаем воркер ARQ на {duration_seconds} секунд для обработки отложенных задач...")
    worker = Worker(
        functions=WorkerSettings.functions, redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup, on_shutdown=WorkerSettings.on_shutdown,
        poll_delay=1
    )
    
    worker_task = asyncio.create_task(worker.main())
    await asyncio.sleep(duration_seconds)
    # Имитируем Ctrl+C для graceful shutdown
    if not worker_task.done():
        worker.handle_sig(signal.SIGINT)
    await worker_task
    print("[WORKER] Воркер завершил работу.")
# backend/tests/utils/task_runner.py

import asyncio
import signal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from arq.connections import create_pool
from arq.worker import Worker

from app.db.models import TaskHistory, User
from app.worker import WorkerSettings
from app.arq_config import redis_settings
from app.tasks.standard_tasks import (
    like_feed_task, add_recommended_friends_task, accept_friend_requests_task,
    remove_friends_by_criteria_task, view_stories_task, birthday_congratulation_task,
    mass_messaging_task, eternal_online_task, leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
)
from app.tasks.system_tasks import (
    publish_scheduled_post_task, run_scenario_from_scheduler_task
)

TASK_FUNCTION_MAP = {
    "like_feed": like_feed_task, "add_recommended": add_recommended_friends_task,
    "accept_friends": accept_friend_requests_task, "remove_friends": remove_friends_by_criteria_task,
    "view_stories": view_stories_task, "birthday_congratulation": birthday_congratulation_task,
    "mass_messaging": mass_messaging_task, "eternal_online": eternal_online_task,
    "leave_groups": leave_groups_by_criteria_task, "join_groups": join_groups_by_criteria_task,
}

# --- НАЧАЛО ИЗМЕНЕНИЯ: Улучшенный TestEmitter ---
class TestEmitter:
    def __init__(self):
        self.logs = []
        self.urls = []

    def set_context(self, user_id: int, task_history_id: int | None = None):
        pass

    async def send_log(self, message: str, status: str, target_url: str | None = None):
        log_entry = f"  - [{status.upper()}] {message}"
        if target_url:
            log_entry += f" -> {target_url}"
            self.urls.append(target_url)
        self.logs.append(log_entry)
    
    async def send_stats_update(self, *args, **kwargs): pass
    async def send_task_status_update(self, *args, **kwargs): pass
    async def send_system_notification(self, *args, **kwargs): pass
# --- КОНЕЦ ИЗМЕНЕНИЯ ---


async def run_and_verify_task(
    async_client: AsyncClient,
    db_session: AsyncSession,
    headers: dict,
    task_key: str,
    payload: dict,
    user: User
) -> TaskHistory:
    print(f"\n--- Тестирование задачи: {task_key} для https://vk.com/id{user.vk_id} ---")
    
    response = await async_client.post(f"/api/v1/tasks/run/{task_key}", headers=headers, json=payload)
    assert response.status_code == 200, f"API вернул ошибку при постановке задачи: {response.text}"
    
    task_history = await db_session.scalar(
        select(TaskHistory).where(TaskHistory.user_id == user.id).order_by(TaskHistory.id.desc())
    )
    assert task_history is not None, "Не удалось найти созданную задачу в БД."
    print(f"[ACTION] Задача '{task_key}' (ID: {task_history.id}, Job ID: {task_history.celery_task_id}) успешно создана в БД.")

    task_function = TASK_FUNCTION_MAP.get(task_key)
    assert task_function is not None, f"Функция для задачи '{task_key}' не найдена."

    print(f"[WORKER-SIM] Выполняем функцию '{task_function.__name__}' напрямую...")
    
    arq_pool = await create_pool(redis_settings)
    worker_context = {'redis_pool': arq_pool}
    
    test_emitter = TestEmitter()
    
    try:
        await task_function(
            worker_context, 
            task_history_id=task_history.id, 
            db_session_for_test=db_session,
            emitter_for_test=test_emitter,
            **payload
        )
    finally:
        await arq_pool.close()

    print("[WORKER-SIM] Выполнение завершено.")

    if test_emitter.logs:
        print("[WORKER-SIM] Логи выполнения:")
        for log_line in test_emitter.logs:
            print(log_line)
            
    if test_emitter.urls:
        print("[VERIFY] Затронутые URL:")
        for url in sorted(list(set(test_emitter.urls))):
            print(f"  -> {url}")
    
    # --- НАЧАЛО ИЗМЕНЕНИЯ: Прикрепляем эмиттер к результату для анализа в тесте ---
    setattr(task_history, 'emitter', test_emitter)
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    print(f"[VERIFY] Финальный статус: {task_history.status}.")
    print(f"[VERIFY] Результат: {task_history.result}")
    
    assert task_history.status == "SUCCESS", f"Ожидался статус SUCCESS, но задача провалилась."
    
    print(f"✓ Задача '{task_key}' прошла успешно.")
    return task_history

async def run_worker_for_duration(duration_seconds: int):
    print(f"[WORKER] Запускаем полноценный воркер ARQ на {duration_seconds} секунд...")
    
    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=WorkerSettings.redis_settings,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        poll_delay=1
    )
    
    worker_task = asyncio.create_task(worker.main())
    
    try:
        await asyncio.sleep(duration_seconds)
    finally:
        if not worker_task.done():
            worker.handle_sig(signal.SIGINT)
        await worker_task
        
    print("[WORKER] Воркер завершил работу.")
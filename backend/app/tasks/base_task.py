# backend/app/tasks/base_task.py
import asyncio
from celery import Task
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.db.models import TaskHistory

# Используем отдельную фабрику сессий для Celery, чтобы избежать проблем с потоками
AsyncSessionFactory_Celery = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class AppBaseTask(Task):
    """
    Кастомный базовый класс для задач Celery, который обрабатывает ошибки
    и обновляет статус в TaskHistory. Теперь поддерживает async-задачи.
    """
    acks_late = True

    async def _update_task_history_async(self, task_history_id: int, status: str, result: str):
        """Асинхронный метод для обновления статуса задачи в БД."""
        if not task_history_id:
            return
        async with AsyncSessionFactory_Celery() as session:
            try:
                task_history = await session.get(TaskHistory, task_history_id)
                if task_history:
                    task_history.status = status
                    task_history.result = result
                    await session.commit()
            except Exception as e:
                print(f"CRITICAL: Failed to update task history {task_history_id}: {e}")

    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: "Умный" запуск async из sync ---
    def _run_async_from_sync(self, coro):
        """
        Надежный способ запустить асинхронную корутину из синхронного кода (сигналов Celery).
        Он корректно работает в окружении, где уже запущен event loop (например, gevent).
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # 'RuntimeError: There is no running event loop'
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coro)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Вызывается, когда задача завершается с ошибкой."""
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        error_message = f"Задача провалена: {exc!r}"
        coro_to_run = self._update_task_history_async(task_history_id, "FAILURE", error_message)
        self._run_async_from_sync(coro_to_run)

    def on_success(self, retval, task_id, args, kwargs):
        """Вызывается при успешном завершении задачи."""
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        success_message = "Задача успешно выполнена."
        coro_to_run = self._update_task_history_async(task_history_id, "SUCCESS", success_message)
        self._run_async_from_sync(coro_to_run)
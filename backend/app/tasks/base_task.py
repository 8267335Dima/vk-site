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
    # Гарантирует, что задача будет подтверждена только после успешного выполнения или провала,
    # что важно для надежности.
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
                # В продакшене здесь должен быть structlog
                print(f"CRITICAL: Failed to update task history {task_history_id}: {e}")

    # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ---
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
        
        # Запускаем корутину в существующем или новом цикле
        return loop.run_until_complete(coro)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Вызывается, когда задача завершается с ошибкой (после всех ретраев)."""
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        error_message = f"Задача провалена: {exc!r}"
        
        # Создаем корутину
        coro_to_run = self._update_task_history_async(task_history_id, "FAILURE", error_message)
        # Запускаем ее безопасно
        self._run_async_from_sync(coro_to_run)

    def on_success(self, retval, task_id, args, kwargs):
        """Вызывается при успешном завершении задачи."""
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        # Важно: retval (результат задачи) не используется для сообщения,
        # так как сервисы сами отправляют детальные логи.
        success_message = "Задача успешно выполнена."

        # Создаем корутину
        coro_to_run = self._update_task_history_async(task_history_id, "SUCCESS", success_message)
        # Запускаем ее безопасно
        self._run_async_from_sync(coro_to_run)
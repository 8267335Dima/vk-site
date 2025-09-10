# backend/app/tasks/base_task.py
import asyncio
from celery import Task
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.db.models import TaskHistory

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
                # Логируем ошибку, если не удалось обновить статус
                # В реальном проекте здесь должен быть полноценный логгер
                print(f"Failed to update task history {task_history_id}: {e}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Вызывается, когда задача завершается с ошибкой (после всех ретраев)."""
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        error_message = f"Задача провалена: {exc!r}"
        # Вынужденное использование asyncio.run(), так как сигналы Celery - синхронные.
        # Это безопасно, так как выполняется в конце жизненного цикла задачи.
        asyncio.run(self._update_task_history_async(task_history_id, "FAILURE", error_message))

    def on_success(self, retval, task_id, args, kwargs):
        """Вызывается при успешном завершении задачи."""
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        success_message = "Задача успешно выполнена."
        asyncio.run(self._update_task_history_async(task_history_id, "SUCCESS", success_message))
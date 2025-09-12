# backend/app/tasks/base_task.py
import asyncio
from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.db.models import TaskHistory
from app.core.config import settings

AsyncSessionFactory_Celery = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(settings.database_url.replace("+asyncpg", ""))
SyncSessionFactory_Celery = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


class AppBaseTask(Task):
    acks_late = True

    def _update_task_history_sync(self, task_history_id: int, status: str, result: str):
        if not task_history_id:
            return
        
        session = SyncSessionFactory_Celery()
        try:
            task_history = session.get(TaskHistory, task_history_id)
            if task_history:
                task_history.status = status
                task_history.result = result
                session.commit()
        except Exception as e:
            print(f"CRITICAL: Failed to update task history {task_history_id}: {e}")
            session.rollback()
        finally:
            session.close()


    def on_failure(self, exc, task_id, args, kwargs, einfo):
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        error_message = f"Задача провалена: {exc!r}"
        self._update_task_history_sync(task_history_id, "FAILURE", error_message)

    def on_success(self, retval, task_id, args, kwargs):
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        success_message = "Задача успешно выполнена."
        self._update_task_history_sync(task_history_id, "SUCCESS", success_message)
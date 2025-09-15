# backend/app/services/event_emitter.py
import datetime
import json
from datetime import UTC 
import structlog
from typing import Literal, Dict, Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Notification

LogLevel = Literal["debug", "info", "success", "warning", "error"]

class RedisEventEmitter:
    # ... (весь код этого класса остается без изменений) ...
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.user_id = None
        self.task_history_id = None

    def set_context(self, user_id: int, task_history_id: int | None = None):
        self.user_id = user_id
        self.task_history_id = task_history_id

    async def _publish(self, channel: str, message: Dict[str, Any]):
        if not self.user_id:
            raise ValueError("User ID must be set before emitting events.")
        await self.redis.publish(channel, json.dumps(message))

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        payload = {
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            "timestamp": datetime.datetime.now(UTC).isoformat(),
            "message": message,
            "status": status,
            "url": target_url,
            "task_history_id": self.task_history_id,
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "log", "payload": payload})

    async def send_stats_update(self, stats_dict: Dict[str, Any]):
        await self._publish(f"ws:user:{self.user_id}", {"type": "stats_update", "payload": stats_dict})

    async def send_task_status_update(self, status: str, result: str | None = None, task_name: str | None = None, created_at: datetime.datetime | None = None):
        if not self.task_history_id: return
        payload = {
            "task_history_id": self.task_history_id, "status": status, "result": result,
            "task_name": task_name, "created_at": created_at.isoformat() if created_at else None
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "task_history_update", "payload": payload})

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        new_notification = Notification(user_id=self.user_id, message=message, level=level)
        db.add(new_notification)
        await db.flush()
        await db.refresh(new_notification)
        payload = { "id": new_notification.id, "message": new_notification.message, "level": new_notification.level,
                    "is_read": new_notification.is_read, "created_at": new_notification.created_at.isoformat() }
        await self._publish(f"ws:user:{self.user_id}", {"type": "new_notification", "payload": payload})

# --- ДОБАВЬТЕ ЭТОТ КЛАСС В КОНЕЦ ФАЙЛА ---
class SystemLogEmitter:
    """
    Эмиттер-заглушка для фоновых задач (cron), который выводит логи в structlog,
    а не отправляет их пользователю через Redis.
    """
    def __init__(self, task_name: str, user_id: int | None = None):
        self.log = structlog.get_logger(task_name)
        if user_id:
            # Привязываем ID пользователя к логам для удобства отладки
            self.log = self.log.bind(user_id=user_id)

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        # Преобразуем статусы в уровни логирования structlog
        if status in ['error', 'warning']:
            # Используем соответствующий уровень для ошибок и предупреждений
            getattr(self.log, status)(message, url=target_url)
        else:
            # Все остальное (info, success, debug) логируем как info
            self.log.info(message, url=target_url, status=status)

    async def send_stats_update(self, stats_dict: Dict[str, Any]):
        # Обновления статистики для UI не нужны в фоновых задачах, просто игнорируем
        pass

    async def send_task_status_update(self, *args, **kwargs):
        # Обновления статуса задачи для UI не нужны, игнорируем
        pass

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        # Системные уведомления от фоновых задач также создаем в БД
        if self.user_id:
             new_notification = Notification(user_id=self.user_id, message=message, level=level)
             db.add(new_notification)
             # коммит будет выполнен в вызывающей функции
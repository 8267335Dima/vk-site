# --- backend/app/services/event_emitter.py ---

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
    """
    Отправляет события в Redis Pub/Sub для实时-обновлений в UI пользователя.
    """
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.user_id: int | None = None
        self.task_history_id: int | None = None

    def set_context(self, user_id: int, task_history_id: int | None = None):
        self.user_id = user_id
        self.task_history_id = task_history_id

    async def _publish(self, channel: str, message: Dict[str, Any]):
        if not self.user_id:
            # Вместо ValueError используем structlog для логирования, чтобы не прерывать выполнение
            structlog.get_logger(__name__).warn("event_emitter.user_id_not_set")
            return
        await self.redis.publish(channel, json.dumps(message))

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        payload = {
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
        if not self.user_id: return
        
        new_notification = Notification(user_id=self.user_id, message=message, level=level)
        db.add(new_notification)
        await db.flush()
        await db.refresh(new_notification)
        
        payload = { 
            "id": new_notification.id, "message": new_notification.message, "level": new_notification.level,
            "is_read": new_notification.is_read, "created_at": new_notification.created_at.isoformat() 
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "new_notification", "payload": payload})


# --- ИСПРАВЛЕНИЕ: Объединенный и улучшенный класс-заглушка ---
class SystemLogEmitter:
    """
    Эмиттер-заглушка для фоновых задач (cron) и сервисов, не требующих UI-отклика.
    Выводит логи в structlog и создает системные уведомления в БД, 
    полностью имитируя интерфейс RedisEventEmitter для совместимости.
    """
    def __init__(self, task_name: str):
        self.log = structlog.get_logger(task_name)
        self.user_id: int | None = None
        self.task_history_id: int | None = None # Для совместимости интерфейса

    def set_context(self, user_id: int, task_history_id: int | None = None):
        """Привязывает ID пользователя к логам для удобства фильтрации и отладки."""
        self.user_id = user_id
        self.task_history_id = task_history_id
        # bind добавляет user_id ко всем последующим логам от этого экземпляра
        self.log = self.log.bind(user_id=user_id)

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        """Преобразует статусы в уровни логирования structlog."""
        # Находим нужный метод логгера (info, warning, error), по умолчанию info
        log_method = getattr(self.log, status, self.log.info)
        log_method(message, url=target_url, status_from_emitter=status)

    async def send_stats_update(self, stats_dict: Dict[str, Any]):
        """Обновления статистики для UI не нужны в фоновых задачах, просто игнорируем."""
        pass

    async def send_task_status_update(self, *args, **kwargs):
        """Обновления статуса задачи для UI не нужны, игнорируем."""
        pass

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        """Системные уведомления от фоновых задач также создаем в БД."""
        if self.user_id:
             new_notification = Notification(user_id=self.user_id, message=message, level=level)
             db.add(new_notification)
             # Коммит будет выполнен в вызывающей функции (в сервисе или задаче)
             self.log.info("system_notification.created", message=message, level=level)
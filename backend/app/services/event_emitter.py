# backend/app/services/event_emitter.py
import datetime
import json
from typing import Literal, Dict, Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Notification, TaskHistory

LogLevel = Literal["debug", "info", "success", "warning", "error"]

class RedisEventEmitter:
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
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "message": message,
            "status": status,
            "url": target_url,
            "task_history_id": self.task_history_id,
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "log", "payload": payload})

    async def send_stats_update(self, stat: str, value: Any):
        await self._publish(f"ws:user:{self.user_id}", {"type": "stats_update", "payload": {"stat": stat, "value": value}})

    async def send_task_status_update(self, status: str, result: str | None = None):
        if not self.task_history_id: return
        payload = {"task_history_id": self.task_history_id, "status": status, "result": result}
        await self._publish(f"ws:user:{self.user_id}", {"type": "task_history_update", "payload": payload})

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        new_notification = Notification(user_id=self.user_id, message=message, level=level)
        db.add(new_notification)
        await db.flush()
        await db.refresh(new_notification)

        payload = {
            "id": new_notification.id,
            "message": new_notification.message,
            "level": new_notification.level,
            "is_read": new_notification.is_read,
            "created_at": new_notification.created_at.isoformat()
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "new_notification", "payload": payload})
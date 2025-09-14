# --- backend/app/api/schemas/notifications.py ---
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List

class Notification(BaseModel):
    id: int
    message: str
    level: str
    is_read: bool
    created_at: datetime

    # ИСПРАВЛЕНО: Замена устаревшего Config на model_config
    model_config = ConfigDict(from_attributes=True)

class NotificationsResponse(BaseModel):
    items: List[Notification]
    unread_count: int
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
    model_config = ConfigDict(from_attributes=True)

class NotificationsResponse(BaseModel):
    items: List[Notification]
    unread_count: int
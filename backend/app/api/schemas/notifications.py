# backend/app/api/schemas/notifications.py
from pydantic import BaseModel
from datetime import datetime
from typing import List

class Notification(BaseModel):
    id: int
    message: str
    level: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationsResponse(BaseModel):
    items: List[Notification]
    unread_count: int
# backend/app/api/schemas/logs.py
import datetime
from pydantic import BaseModel
from typing import List, Optional

class ActionLogEntry(BaseModel):
    id: int
    action_type: str
    message: str
    target_url: Optional[str] = None
    status: str
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class PaginatedLogsResponse(BaseModel):
    items: List[ActionLogEntry]
    total: int
    page: int
    size: int
    has_more: bool
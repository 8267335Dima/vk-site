# backend/app/api/schemas/tasks.py
import datetime
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class TaskHistoryRead(BaseModel):
    id: int
    celery_task_id: str
    task_name: str
    status: str
    parameters: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class PaginatedTasksResponse(BaseModel):
    items: List[TaskHistoryRead]
    total: int
    page: int
    size: int
    has_more: bool
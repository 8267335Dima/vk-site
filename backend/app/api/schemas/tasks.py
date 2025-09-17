# backend/app/api/schemas/tasks.py
import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Literal, Optional, Dict, Any

# --- Схема для ответа после запуска любой задачи ---
class ActionResponse(BaseModel):
    status: str = "success"
    message: str
    task_id: str

class TaskHistoryRead(BaseModel):
    id: int
    arq_job_id: Optional[str] = None
    task_name: str
    status: str
    parameters: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    model_config = ConfigDict(from_attributes=True)


class PaginatedTasksResponse(BaseModel):
    items: List[TaskHistoryRead]
    total: int
    page: int
    size: int
    has_more: bool

class PreviewResponse(BaseModel):
    found_count: int

class TaskField(BaseModel):
    name: str
    type: Literal["slider", "switch", "text"]
    label: str
    default_value: Any
    max_value: Optional[int] = None
    tooltip: Optional[str] = None

class TaskConfigResponse(BaseModel):
    display_name: str
    has_filters: bool
    fields: List[TaskField]
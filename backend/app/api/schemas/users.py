# backend/app/api/schemas/users.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Literal
from datetime import datetime

class UserBase(BaseModel):
    id: int
    vk_id: int
    model_config = ConfigDict(from_attributes=True)

class ProxyUpdateRequest(BaseModel):
    proxy: Optional[str] = Field(None, description="Строка прокси, например http://user:pass@host:port")

class UserMeResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    photo_200: str
    status: str = ""
    counters: Optional[Dict[str, Any]] = None
    plan: str
    plan_expires_at: Optional[datetime] = None
    is_admin: bool
    delay_profile: str
    proxy: Optional[str] = None

class TaskInfoResponse(BaseModel):
    count: int
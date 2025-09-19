# backend/app/api/schemas/support.py

from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from datetime import datetime
from typing import List, Optional

class TicketMessageRead(BaseModel):
    id: int
    author_id: int
    message: str
    attachment_url: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TicketMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    attachment_url: Optional[HttpUrl] = None

class SupportTicketRead(BaseModel):
    id: int
    user_id: int
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    messages: List[TicketMessageRead] = []
    model_config = ConfigDict(from_attributes=True)
    
class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=5, max_length=100)
    message: str = Field(..., min_length=10, max_length=5000)
    attachment_url: Optional[HttpUrl] = None

class SupportTicketList(BaseModel):
    id: int
    subject: str
    status: str
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)
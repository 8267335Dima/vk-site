from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List

# --- Схемы для сообщений ---
class TicketMessageRead(BaseModel):
    id: int
    author_id: int
    message: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TicketMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)

# --- Схемы для тикетов ---
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

class SupportTicketList(BaseModel):
    """Схема для отображения в списке, без сообщений."""
    id: int
    subject: str
    status: str
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)
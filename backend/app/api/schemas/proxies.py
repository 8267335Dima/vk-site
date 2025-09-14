# --- backend/app/api/schemas/proxies.py ---
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class ProxyBase(BaseModel):
    proxy_url: str = Field(..., description="Строка прокси, например http://user:pass@host:port")

class ProxyCreate(ProxyBase):
    pass

class ProxyRead(ProxyBase):
    id: int
    is_working: bool
    last_checked_at: datetime
    check_status_message: str | None = None
    model_config = ConfigDict(from_attributes=True)

class ProxyTestResponse(BaseModel):
    is_working: bool
    status_message: str
# backend/app/core/schemas/config.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class AutomationConfig(BaseModel):
    id: str
    name: str
    description: str
    has_filters: bool
    has_count_slider: bool
    modal_count_label: Optional[str] = None
    default_count: Optional[int] = None
    group: Optional[Literal["standard", "online", "content"]] = "standard"

class PlanPeriod(BaseModel):
    months: int = Field(..., gt=0)
    discount_percent: float = Field(..., ge=0, le=100)

class PlanLimits(BaseModel):
    daily_likes_limit: int = Field(..., ge=0)
    daily_add_friends_limit: int = Field(..., ge=0)
    daily_message_limit: int = Field(..., ge=0)  # <--- ДОБАВЛЕНО
    daily_posts_limit: int = Field(..., ge=0)    # <--- ДОБАВЛЕНО
    max_concurrent_tasks: int = Field(..., ge=1)
    max_profiles: Optional[int] = Field(None, ge=1)
    max_team_members: Optional[int] = Field(None, ge=1)

class PlanConfig(BaseModel):
    display_name: str
    description: str
    limits: PlanLimits
    available_features: List[str] | Literal["*"]
    base_price: Optional[float] = Field(None, ge=0)
    is_popular: Optional[bool] = False
    periods: Optional[List[PlanPeriod]] = []
    features: Optional[List[str]] = []
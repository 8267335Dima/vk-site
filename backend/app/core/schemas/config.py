from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

class CronSettings(BaseModel):
    automation_job_lock_seconds: int
    humanize_online_skip_chance: float

class TaskHistorySettings(BaseModel):
    retention_days_pro: int
    retention_days_base: int

class AppSettings(BaseModel):
    cron: CronSettings
    task_history: TaskHistorySettings

class AutomationConfig(BaseModel):
    id: str
    name: str
    description: str
    has_filters: bool
    has_count_slider: bool
    modal_count_label: Optional[str] = None
    default_count: Optional[int] = None
    group: Optional[Literal["standard", "online", "content", "ai", "parsing"]] = "standard"
    default_settings: Optional[Dict[str, Any]] = None

class PlanPeriod(BaseModel):
    months: int = Field(..., gt=0)
    discount_percent: float = Field(..., ge=0, le=100)

class PlanLimits(BaseModel):
    daily_likes_limit: int = Field(..., ge=0)
    daily_add_friends_limit: int = Field(..., ge=0)
    daily_message_limit: int = Field(..., ge=0) 
    daily_posts_limit: int = Field(..., ge=0)   
    daily_join_groups_limit: int = Field(..., ge=0)
    daily_leave_groups_limit: int = Field(..., ge=0)
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
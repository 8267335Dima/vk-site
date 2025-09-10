# backend/app/api/schemas/analytics.py
from pydantic import BaseModel, Field
from typing import List
from datetime import date

class AudienceStatItem(BaseModel):
    name: str = Field(..., description="Название (город, возрастная группа)")
    value: int = Field(..., description="Количество пользователей")

class AudienceAnalyticsResponse(BaseModel):
    city_distribution: List[AudienceStatItem]
    age_distribution: List[AudienceStatItem]

class FunnelStage(BaseModel):
    stage_name: str
    value: int
    description: str

class FriendsFunnelResponse(BaseModel):
    period_start: date
    period_end: date
    funnel: List[FunnelStage]

class FriendsDynamicItem(BaseModel):
    date: date
    total_friends: int

class FriendsDynamicResponse(BaseModel):
    data: List[FriendsDynamicItem]

# --- НОВЫЕ СХЕМЫ для нового графика ---
class ActionSummaryItem(BaseModel):
    date: date
    total_actions: int

class ActionSummaryResponse(BaseModel):
    data: List[ActionSummaryItem]
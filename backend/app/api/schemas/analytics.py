# backend/app/api/schemas/analytics.py
from pydantic import BaseModel, Field
from typing import List
from datetime import date

class AudienceStatItem(BaseModel):
    name: str = Field(..., description="Название (город, возрастная группа)")
    value: int = Field(..., description="Количество пользователей")

class SexDistributionResponse(BaseModel):
    name: str
    value: int

class AudienceAnalyticsResponse(BaseModel):
    city_distribution: List[AudienceStatItem]
    age_distribution: List[AudienceStatItem]
    sex_distribution: List[SexDistributionResponse]

class FriendsDynamicItem(BaseModel):
    date: date
    total_friends: int

class FriendsDynamicResponse(BaseModel):
    data: List[FriendsDynamicItem]

class ActionSummaryItem(BaseModel):
    date: date
    total_actions: int

class ActionSummaryResponse(BaseModel):
    data: List[ActionSummaryItem]

class ProfileGrowthItem(BaseModel):
    date: date
    total_likes_on_content: int
    friends_count: int

class ProfileGrowthResponse(BaseModel):
    data: List[ProfileGrowthItem]
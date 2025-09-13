# --- backend/app/api/schemas/analytics.py ---
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

class ProfileSummaryResponse(BaseModel):
    friends: int
    followers: int
    photos: int
    wall_posts: int

class ProfileGrowthItem(BaseModel):
    date: date
    total_likes_on_content: int
    friends_count: int

class ProfileGrowthResponse(BaseModel):
    data: List[ProfileGrowthItem]

class FriendRequestConversionResponse(BaseModel):
    sent_total: int
    accepted_total: int
    conversion_rate: float = Field(..., ge=0, le=100)

class PostActivityHeatmapResponse(BaseModel):
    data: List[List[int]] = Field(..., description="Матрица 7x24, где data[day][hour] = уровень активности от 0 до 100")
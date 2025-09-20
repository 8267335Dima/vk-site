# --- START OF FILE backend/app/api/schemas/analytics.py ---

import datetime
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
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

class ProfileSummaryData(BaseModel):
    friends: int = 0
    followers: int = 0
    photos: int = 0
    wall_posts: int = 0
    recent_post_likes: int = 0
    recent_photo_likes: int = 0
    total_post_likes: int = 0
    total_photo_likes: int = 0

class ProfileSummaryResponse(BaseModel):
    current_stats: ProfileSummaryData
    growth_daily: Dict[str, int]
    growth_weekly: Dict[str, int]


class ProfileGrowthItem(BaseModel):
    date: date
    friends_count: int
    followers_count: int
    photos_count: int
    wall_posts_count: int
    recent_post_likes: int
    recent_photo_likes: int
    total_post_likes: int
    total_photo_likes: int


class ProfileGrowthResponse(BaseModel):
    data: List[ProfileGrowthItem]

class FriendRequestConversionResponse(BaseModel):
    sent_total: int
    accepted_total: int
    conversion_rate: float = Field(..., ge=0, le=100)

class PostActivityHeatmapResponse(BaseModel):
    data: List[List[int]] = Field(..., description="Матрица 7x24, где data[day][hour] = уровень активности от 0 до 100")


class PostActivityRecommendation(BaseModel):
    day_of_week: str
    hour_start: int
    activity_score: int # от 0 до 100

class PostActivityRecommendationsResponse(BaseModel):
    recommendations: List[PostActivityRecommendation]
    last_updated_at: Optional[datetime.datetime] = None
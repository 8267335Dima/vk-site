# backend/app/api/schemas/stats.py
from pydantic import BaseModel
from typing import List
from datetime import date

class FriendsAnalyticsResponse(BaseModel):
    male_count: int
    female_count: int
    other_count: int

class DailyActivity(BaseModel):
    date: date
    likes: int
    friends_added: int
    requests_accepted: int

class ActivityStatsResponse(BaseModel):
    period_days: int
    data: List[DailyActivity]

# --- НОВЫЕ СХЕМЫ ---
class FriendsDynamicItem(BaseModel):
    date: date
    total_friends: int

class FriendsDynamicResponse(BaseModel):
    data: List[FriendsDynamicItem]
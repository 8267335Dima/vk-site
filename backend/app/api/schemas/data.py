# backend/app/api/schemas/data.py
from pydantic import BaseModel, Field

class ParsingFilters(BaseModel):
    posts_depth: int = Field(10, ge=1, le=100, description="Глубина анализа постов на стене.")

class ParsingRequest(BaseModel):
    group_id: int = Field(..., gt=0)
    filters: ParsingFilters = Field(default_factory=ParsingFilters)

class GroupMembersParsingRequest(BaseModel):
    group_id: int = Field(..., gt=0)
    count: int = Field(1000, ge=1, le=1000)

class UserWallParsingRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    count: int = Field(100, ge=1, le=100)

class TopUsersParsingRequest(BaseModel):
    group_id: int = Field(..., gt=0)
    posts_depth: int = Field(20, ge=1, le=100)
    top_n: int = Field(10, ge=1, le=100)

class UserInfo(BaseModel):
    id: int
    first_name: str
    last_name: str
    photo_100: str
    online: int

class TopUserResponse(BaseModel):
    user_info: UserInfo
    activity_score: int
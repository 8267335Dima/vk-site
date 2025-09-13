# --- backend/app/api/schemas/teams.py --- (НОВЫЙ ФАЙЛ)
from pydantic import BaseModel, Field
from typing import List

class ProfileInfo(BaseModel):
    id: int
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str

class TeamMemberAccess(BaseModel):
    profile: ProfileInfo
    has_access: bool

class TeamMemberRead(BaseModel):
    id: int
    user_id: int
    user_info: ProfileInfo
    role: str
    accesses: List[TeamMemberAccess]

class TeamRead(BaseModel):
    id: int
    name: str
    owner_id: int
    members: List[TeamMemberRead]

class TeamCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)

class InviteMemberRequest(BaseModel):
    user_vk_id: int

class UpdateAccessRequest(BaseModel):
    profile_user_id: int
    has_access: bool
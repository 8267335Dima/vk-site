# --- backend/app/api/schemas/teams.py ---
from pydantic import BaseModel, Field, ConfigDict
from typing import List

class ProfileInfo(BaseModel):
    id: int
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str
    
    # ДОБАВЛЕНО: Для корректной работы с ORM-моделями
    model_config = ConfigDict(from_attributes=True)

class TeamMemberAccess(BaseModel):
    profile: ProfileInfo
    has_access: bool
    
    # ДОБАВЛЕНО: Для корректной работы с ORM-моделями
    model_config = ConfigDict(from_attributes=True)

class TeamMemberRead(BaseModel):
    id: int
    user_id: int
    user_info: ProfileInfo
    role: str
    accesses: List[TeamMemberAccess]
    
    # ДОБАВЛЕНО: Для корректной работы с ORM-моделями
    model_config = ConfigDict(from_attributes=True)

class TeamRead(BaseModel):
    id: int
    name: str
    owner_id: int
    members: List[TeamMemberRead]
    
    # ДОБАВЛЕНО: Для корректной работы с ORM-моделями
    model_config = ConfigDict(from_attributes=True)

class TeamCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)

class InviteMemberRequest(BaseModel):
    user_vk_id: int

class UpdateAccessRequest(BaseModel):
    profile_user_id: int
    has_access: bool
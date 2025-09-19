# backend/app/api/schemas/groups.py
from pydantic import BaseModel, Field
from typing import List

class GroupBase(BaseModel):
    vk_group_id: int
    name: str
    photo_100: str | None = None

class GroupRead(GroupBase):
    id: int

    class Config:
        from_attributes = True

class AddGroupRequest(BaseModel):
    vk_group_id: int = Field(..., gt=0)
    access_token: str

class AvailableGroupsResponse(BaseModel):
    groups: List[GroupRead]
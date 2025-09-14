# --- backend/app/api/schemas/users.py ---
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any

class UserBase(BaseModel):
    id: int
    vk_id: int
    model_config = ConfigDict(from_attributes=True)

class TaskInfoResponse(BaseModel):
    count: int

class FilterPresetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    action_type: str
    filters: Dict[str, Any]

class FilterPresetCreate(FilterPresetBase):
    pass

class FilterPresetRead(FilterPresetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ManagedProfileRead(BaseModel):
    id: int
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str
    model_config = ConfigDict(from_attributes=True)
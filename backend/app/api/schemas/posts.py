# --- backend/app/api/schemas/posts.py ---
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional

class PostBase(BaseModel):
    post_text: Optional[str] = None
    attachments: Optional[List[str]] = Field(default_factory=list)
    publish_at: datetime

class PostCreate(PostBase):
    pass

class PostUpdate(PostBase):
    pass

class PostRead(PostBase):
    id: int
    vk_profile_id: int
    status: str
    vk_post_id: Optional[str] = None
    error_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UploadedImageResponse(BaseModel):
    attachment_id: str
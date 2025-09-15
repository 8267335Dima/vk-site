# --- backend/app/api/schemas/posts.py ---
from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from datetime import datetime
from typing import List, Optional

class PostBase(BaseModel):
    post_text: Optional[str] = None
    publish_at: datetime

class PostCreate(PostBase):
    attachments: Optional[List[str]] = Field(default_factory=list, description="Список готовых attachment ID (photo_id, etc.)")
    image_url: Optional[HttpUrl] = Field(None, description="URL изображения для автоматической загрузки и прикрепления.")

class PostRead(PostBase):
    id: int
    vk_profile_id: int
    attachments: Optional[List[str]] = None
    status: str
    vk_post_id: Optional[str] = None
    error_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UploadedImageResponse(BaseModel): 
    attachment_id: str

class UploadedImagesResponse(BaseModel):
    """Ответ для пакетной загрузки изображений."""
    attachment_ids: List[str]

class PostBatchCreate(BaseModel):
    """Схема для пакетного создания постов."""
    posts: List[PostCreate]
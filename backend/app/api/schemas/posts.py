# backend/app/api/schemas/posts.py
from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from datetime import datetime
from typing import List, Optional

class PostBase(BaseModel):
    post_text: Optional[str] = Field(None, max_length=4000)
    publish_at: datetime

class PostCreate(PostBase):
    attachments: Optional[List[str]] = Field(
        default_factory=list, 
        description="Список готовых attachment ID (photo_id, etc.). Не более 10.",
        max_length=10 # <--- ИЗМЕНЕНИЕ: max_items -> max_length
    )
    from_group_id: Optional[int] = Field(None, description="ID группы, от имени которой нужно опубликовать пост.")

class PostRead(PostBase):
    id: int
    vk_profile_id: int
    attachments: Optional[List[str]] = None
    status: str
    vk_post_id: Optional[str] = None
    error_message: Optional[str] = None
    arq_job_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UploadedImageResponse(BaseModel): 
    attachment_id: str

class UploadImageFromUrlRequest(BaseModel):
    image_url: HttpUrl

class UploadedImagesResponse(BaseModel):
    attachment_ids: List[str]

class UploadImagesFromUrlsRequest(BaseModel):
    image_urls: List[HttpUrl] = Field(..., description="Список URL изображений для загрузки. Не более 10.", max_length=10) # <--- ИЗМЕНЕНИЕ: max_items -> max_length

class PostBatchCreate(BaseModel):
    posts: List[PostCreate]

class PostUpdateSchedule(BaseModel):
    publish_at: datetime
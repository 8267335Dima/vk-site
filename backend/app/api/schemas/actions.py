# backend/app/api/schemas/actions.py

from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class ActionFilters(BaseModel):
    """Общая модель для фильтров."""
    sex: Optional[Literal[0, 1, 2]] = 0 
    is_online: Optional[bool] = False
    last_seen_days: Optional[int] = Field(None, ge=1)
    last_seen_hours: Optional[int] = Field(None, ge=1)
    allow_closed_profiles: bool = False
    # Фильтр для чистки друзей, здесь для универсальности
    remove_banned: Optional[bool] = True
    # --- НОВЫЕ ПОЛЯ для приема заявок ---
    min_friends: Optional[int] = Field(None, ge=0)
    max_friends: Optional[int] = Field(None, ge=0)
    min_followers: Optional[int] = Field(None, ge=0)
    max_followers: Optional[int] = Field(None, ge=0)


class LikeFriendsFeedRequest(BaseModel):
    count: int = Field(50, ge=1, le=1000)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class LikeFeedRequest(BaseModel):
    count: int = Field(50, ge=1, le=1000)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']
    count: int = Field(1, ge=1, le=3)

class ViewStoriesRequest(BaseModel):
    filters: ActionFilters = Field(default_factory=ActionFilters)

# --- ИЗМЕНЕНИЕ: Добавлены поля для сообщения при добавлении ---
class AddFriendsRequest(BaseModel):
    count: int = Field(20, ge=1, le=100)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    like_config: LikeAfterAddConfig = Field(default_factory=LikeAfterAddConfig)
    send_message_on_add: bool = False
    message_text: Optional[str] = Field(None, max_length=500)


class AcceptFriendsRequest(BaseModel):
    """Схема приема заявок теперь не содержит count."""
    filters: ActionFilters = Field(default_factory=ActionFilters)

class RemoveFriendsRequest(BaseModel):
    count: int = Field(500, ge=1, le=1000)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class ActionResponse(BaseModel):
    status: str = "success"
    message: str
    task_id: str
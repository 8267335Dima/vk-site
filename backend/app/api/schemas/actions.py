# --- backend/app/api/schemas/actions.py ---
from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class ActionFilters(BaseModel):
    sex: Optional[Literal[0, 1, 2]] = 0 
    is_online: Optional[bool] = False
    last_seen_hours: Optional[int] = Field(None, ge=1)
    allow_closed_profiles: bool = False
    status_keyword: Optional[str] = Field(None, max_length=100)
    only_with_photo: Optional[bool] = Field(False, description="Применять действие только к постам с фотографиями")
    
    remove_banned: Optional[bool] = True
    last_seen_days: Optional[int] = Field(None, ge=1)

    min_friends: Optional[int] = Field(None, ge=0)
    max_friends: Optional[int] = Field(None, ge=0)
    min_followers: Optional[int] = Field(None, ge=0)
    max_followers: Optional[int] = Field(None, ge=0)

class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']

class BaseCountRequest(BaseModel):
    count: int = Field(50, ge=1)

class AddFriendsRequest(BaseCountRequest):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    like_config: LikeAfterAddConfig = Field(default_factory=LikeAfterAddConfig)
    send_message_on_add: bool = False
    message_text: Optional[str] = Field(None, max_length=500)

class LikeFeedRequest(BaseCountRequest):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class RemoveFriendsRequest(BaseCountRequest):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class AcceptFriendsRequest(BaseModel):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class MassMessagingRequest(BaseCountRequest):
    filters: ActionFilters = Field(default_factory=ActionFilters)
    message_text: str = Field(..., min_length=1, max_length=1000)
    only_new_dialogs: bool = Field(False, description="Отправлять только тем, с кем еще не было переписки.")

class LeaveGroupsRequest(BaseCountRequest):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class JoinGroupsRequest(BaseCountRequest):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class EmptyRequest(BaseModel):
    pass
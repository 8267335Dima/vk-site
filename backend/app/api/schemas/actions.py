# --- backend/app/api/schemas/actions.py ---
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Any

class ActionFilters(BaseModel):
    sex: Optional[Literal[0, 1, 2]] = Field(0, description="0 - любой, 1 - жен, 2 - муж")
    is_online: Optional[bool] = False
    last_seen_hours: Optional[int] = Field(None, ge=1, description="Фильтр по последнему визиту в часах")
    allow_closed_profiles: bool = False
    status_keyword: Optional[str] = Field(None, max_length=100)
    only_with_photo: Optional[bool] = Field(False, description="Применять только к постам с фото (для like_feed)")

    # Для remove_friends
    remove_banned: Optional[bool] = True
    last_seen_days: Optional[int] = Field(None, ge=1, description="Фильтр по последнему визиту в днях")

    # Для accept_friends
    min_friends: Optional[int] = Field(None, ge=0)
    max_friends: Optional[int] = Field(None, ge=0)
    min_followers: Optional[int] = Field(None, ge=0)
    max_followers: Optional[int] = Field(None, ge=0)

class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']

# --- Модели для каждой задачи ---

class LikeFeedRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class AddFriendsRequest(BaseModel):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    like_config: LikeAfterAddConfig = Field(default_factory=LikeAfterAddConfig)
    send_message_on_add: bool = False
    message_text: Optional[str] = Field(None, max_length=500)

class AcceptFriendsRequest(BaseModel):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class RemoveFriendsRequest(BaseModel):
    count: int = Field(100, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class MassMessagingRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    message_text: str = Field(..., min_length=1, max_length=1000)
    only_new_dialogs: bool = Field(False, description="Отправлять только тем, с кем еще не было переписки.")

class LeaveGroupsRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class JoinGroupsRequest(BaseModel):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class EmptyRequest(BaseModel):
    pass

class BirthdayCongratulationRequest(BaseModel):
    message_template_default: str = "С Днем Рождения, {name}!"
    message_template_male: Optional[str] = None
    message_template_female: Optional[str] = None

# --- Для динамической конфигурации UI ---
class TaskField(BaseModel):
    name: str
    type: Literal["slider", "switch", "text"]
    label: str
    default_value: Any
    max_value: Optional[int] = None
    tooltip: Optional[str] = None

class TaskConfigResponse(BaseModel):
    display_name: str
    has_filters: bool
    fields: List[TaskField]
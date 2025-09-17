# --- backend/app/api/schemas/actions.py ---
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, List, Any, Dict
import re


class ActionFilters(BaseModel):
    sex: Optional[Literal[0, 1, 2]] = Field(0, description="0 - любой, 1 - жен, 2 - муж")
    is_online: Optional[bool] = False
    last_seen_hours: Optional[int] = Field(None, ge=1)
    allow_closed_profiles: bool = False
    status_keyword: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    only_with_photo: Optional[bool] = Field(False)
    remove_banned: Optional[bool] = True
    last_seen_days: Optional[int] = Field(None, ge=1)
    
class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']

# --- НОВАЯ СХЕМА ДЛЯ "УМНОЙ" ОТПРАВКИ ---
class HumanizedSendingConfig(BaseModel):
    enabled: bool = Field(False, description="Включить режим 'человечной' отправки (медленно, по одному)")
    speed: Literal["slow", "normal", "fast"] = Field("normal", description="Скорость набора и отправки")
    simulate_typing: bool = Field(True, description="Показывать статус 'набирает сообщение'")


# --- Обновленные модели для задач ---

class LikeFeedRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class AddFriendsRequest(BaseModel):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    like_config: LikeAfterAddConfig = Field(default_factory=LikeAfterAddConfig)
    send_message_on_add: bool = False
    message_text: Optional[str] = Field(None, max_length=500)
    # ДОБАВЛЕНО: Настройки очеловечивания для приветственного сообщения
    humanized_sending: HumanizedSendingConfig = Field(default_factory=HumanizedSendingConfig)


class AcceptFriendsRequest(BaseModel):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class RemoveFriendsRequest(BaseModel):
    count: int = Field(100, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class MassMessagingRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    message_text: str = Field(..., min_length=1, max_length=1000)
    attachments: Optional[List[str]] = Field(
        None,
        description="Список attachment ID (напр. 'photo123_456').",
        max_length=10
    )
    # ------------------
    only_new_dialogs: bool = Field(False)
    only_unread: bool = Field(False)
    humanized_sending: HumanizedSendingConfig = Field(default_factory=HumanizedSendingConfig)


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
    filters: ActionFilters = Field(default_factory=ActionFilters)
    only_new_dialogs: bool = Field(False)
    only_unread: bool = Field(False)
    humanized_sending: HumanizedSendingConfig = Field(default_factory=HumanizedSendingConfig)


class DaySchedule(BaseModel):
    """Схема для расписания на один день."""
    is_active: bool = True
    start_time: str = Field("09:00", description="Время начала в формате HH:MM")
    end_time: str = Field("23:00", description="Время окончания в формате HH:MM")

    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not re.match(r'^(?:[01]\d|2[0-3]):[0-5]\d$', v):
            raise ValueError('Неверный формат времени. Ожидается HH:MM')
        return v
    
    @model_validator(mode='after')
    def check_times_logic(self) -> 'DaySchedule':
        start = self.start_time
        end = self.end_time
        if start >= end:
            raise ValueError('Время начала должно быть раньше времени окончания')
        return self

class EternalOnlineRequest(BaseModel):
    """
    ФИНАЛЬНАЯ ВЕРСИЯ: Отдельная, полноценная модель для задачи "Статус 'Онлайн'".
    """
    mode: Literal["schedule", "always"] = "schedule"
    humanize: bool = True
    schedule_weekly: Dict[Literal["1", "2", "3", "4", "5", "6", "7"], DaySchedule] = Field(
        default_factory=dict
    )
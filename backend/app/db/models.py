# --- backend/app/db/models.py ---
import datetime
import enum
from sqlalchemy import (
    Column, Float, Integer, String, DateTime, ForeignKey, BigInteger, Date,
    UniqueConstraint, text, Enum, Boolean, Index, JSON, Text
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class DelayProfile(enum.Enum):
    slow = "slow"
    normal = "normal"
    fast = "fast"

class FriendRequestStatus(enum.Enum):
    pending = "pending"
    accepted = "accepted"

class ScenarioStepType(enum.Enum):
    action = "action"
    condition = "condition"

class PostActivityHeatmap(Base):
    __tablename__ = "post_activity_heatmaps"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    heatmap_data = Column(JSON, nullable=False) # Хранит матрицу 7x24
    last_updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="heatmap")

class ScheduledPostStatus(enum.Enum):
    scheduled = "scheduled"
    published = "published"
    failed = "failed"

class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vk_profile_id = Column(BigInteger, nullable=False, index=True) # ID профиля, на стену которого публикуем
    post_text = Column(Text, nullable=True)
    attachments = Column(JSON, nullable=True) # Хранит список attachment_id
    publish_at = Column(DateTime, nullable=False, index=True)
    status = Column(Enum(ScheduledPostStatus), nullable=False, default=ScheduledPostStatus.scheduled, index=True)
    celery_task_id = Column(String, nullable=True, unique=True)
    vk_post_id = Column(String, nullable=True) # ID опубликованного поста
    error_message = Column(Text, nullable=True)

    user = relationship("User")

class TeamMemberRole(enum.Enum):
    admin = "admin"
    member = "member"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    vk_id = Column(BigInteger, unique=True, index=True, nullable=False)
    encrypted_vk_token = Column(String, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    plan = Column(String, nullable=False, server_default='Базовый')
    plan_expires_at = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, nullable=False, server_default='false')

    daily_likes_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_add_friends_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_message_limit = Column(Integer, nullable=False, server_default=text('0'))
    
    delay_profile = Column(Enum(DelayProfile), nullable=False, server_default=DelayProfile.normal.name)

    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    task_history = relationship("TaskHistory", back_populates="user", cascade="all, delete-orphan")
    daily_stats = relationship("DailyStats", back_populates="user", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")
    profile_metrics = relationship("ProfileMetric", back_populates="user", cascade="all, delete-orphan")
    filter_presets = relationship("FilterPreset", back_populates="user", cascade="all, delete-orphan")
    friend_requests = relationship("FriendRequestLog", back_populates="user", cascade="all, delete-orphan")
    heatmap = relationship("PostActivityHeatmap", back_populates="user", uselist=False, cascade="all, delete-orphan")
    managed_profiles = relationship("ManagedProfile", foreign_keys="[ManagedProfile.manager_user_id]", back_populates="manager", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")
    scheduled_posts = relationship("ScheduledPost", back_populates="user", cascade="all, delete-orphan", foreign_keys="[ScheduledPost.user_id]")

    owned_team = relationship("Team", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    team_membership = relationship("TeamMember", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    owner = relationship("User", back_populates="owned_team")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    role = Column(Enum(TeamMemberRole), nullable=False, default=TeamMemberRole.member)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_membership")
    profile_accesses = relationship("TeamProfileAccess", back_populates="team_member", cascade="all, delete-orphan")
    
    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='_team_user_uc'),)

class TeamProfileAccess(Base):
    __tablename__ = "team_profile_access"
    id = Column(Integer, primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False)
    # ID управляемого профиля (ссылается на User, т.к. профили - это тоже юзеры)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    team_member = relationship("TeamMember", back_populates="profile_accesses")
    profile = relationship("User")

class ManagedProfile(Base):
    __tablename__ = "managed_profiles"
    id = Column(Integer, primary_key=True)
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    manager = relationship("User", foreign_keys=[manager_user_id], back_populates="managed_profiles")
    profile = relationship("User", foreign_keys=[profile_user_id])
    
    __table_args__ = (
        UniqueConstraint('manager_user_id', 'profile_user_id', name='_manager_profile_uc'),
    )

class FriendRequestLog(Base):
    __tablename__ = "friend_request_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_vk_id = Column(BigInteger, nullable=False, index=True)
    status = Column(Enum(FriendRequestStatus), nullable=False, default=FriendRequestStatus.pending, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="friend_requests")
    __table_args__ = (
        UniqueConstraint('user_id', 'target_vk_id', name='_user_target_uc'),
    )

class FilterPreset(Base):
    __tablename__ = "filter_presets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    action_type = Column(String, nullable=False, index=True)
    filters = Column(JSON, nullable=False)

    user = relationship("User", back_populates="filter_presets")
    __table_args__ = (
        UniqueConstraint('user_id', 'name', 'action_type', name='_user_name_action_uc'),
    )

class LoginHistory(Base):
    __tablename__ = "login_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    user = relationship("User")

class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_proxy_url = Column(String, nullable=False)
    is_working = Column(Boolean, default=True, nullable=False, index=True)
    last_checked_at = Column(DateTime, default=datetime.datetime.utcnow)
    check_status_message = Column(String, nullable=True)
    
    user = relationship("User", back_populates="proxies")
    __table_args__ = (
        UniqueConstraint('user_id', 'encrypted_proxy_url', name='_user_proxy_uc'),
    )

class TaskHistory(Base):
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    celery_task_id = Column(String, unique=True, nullable=True, index=True)
    task_name = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING", nullable=False, index=True)
    parameters = Column(JSON, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="task_history")
    __table_args__ = (
        Index('ix_task_history_user_status', 'user_id', 'status'),
    )

class Automation(Base):
    __tablename__ = "automations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_type = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=False, nullable=False)
    settings = Column(JSON, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="automations")
    __table_args__ = (
        UniqueConstraint('user_id', 'automation_type', name='_user_automation_uc'),
    )

class DailyStats(Base):
    __tablename__ = "daily_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    like_friends_feed_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    stories_viewed_count = Column(Integer, default=0, nullable=False)
    friends_removed_count = Column(Integer, default=0, nullable=False)
    messages_sent_count = Column(Integer, default=0, nullable=False)
    
    user = relationship("User", back_populates="daily_stats")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_uc'),
        Index('ix_daily_stats_user_date', 'user_id', 'date'),
    )

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    payment_system_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending", nullable=False)
    plan_name = Column(String, nullable=False)
    months = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = relationship("User")

class Scenario(Base):
    __tablename__ = "scenarios"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    schedule = Column(String, nullable=False) # CRON-строка остается для планировщика
    is_active = Column(Boolean, default=False, nullable=False)
    first_step_id = Column(Integer, ForeignKey("scenario_steps.id", use_alter=True, name="fk_scenario_first_step"), nullable=True)

    user = relationship("User", back_populates="scenarios")
    steps = relationship("ScenarioStep", back_populates="scenario", cascade="all, delete-orphan", foreign_keys="[ScenarioStep.scenario_id]")

class ScenarioStep(Base):
    __tablename__ = "scenario_steps"
    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    
    # Новые поля для графа
    step_type = Column(Enum(ScenarioStepType), nullable=False)
    details = Column(JSON, nullable=False) # Хранит тип действия/условия и их параметры
    
    # Указатели на следующие шаги
    next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True) # Для 'action'
    on_success_next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True) # Для 'condition'
    on_failure_next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True) # Для 'condition'

    # UI-координаты для React Flow
    position_x = Column(Float, default=0)
    position_y = Column(Float, default=0)

    scenario = relationship("Scenario", back_populates="steps", foreign_keys=[scenario_id])

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String, nullable=False)
    level = Column(String, default="info", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    user = relationship("User", back_populates="notifications")

class ProfileMetric(Base):
    __tablename__ = "profile_metrics"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    total_likes_on_content = Column(Integer, nullable=False)
    friends_count = Column(Integer, nullable=False)

    user = relationship("User", back_populates="profile_metrics")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_metric_uc'),
        Index('ix_profile_metrics_user_date', 'user_id', 'date'),
    )

class WeeklyStats(Base):
    __tablename__ = "weekly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_identifier = Column(String, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'week_identifier', name='_user_week_uc'),
    )

class MonthlyStats(Base):
    __tablename__ = "monthly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month_identifier = Column(String, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'month_identifier', name='_user_month_uc'),
    )

class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    user = relationship("User")

class SentCongratulation(Base):
    __tablename__ = "sent_congratulations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_vk_id = Column(BigInteger, nullable=False, index=True)
    year = Column(Integer, nullable=False)

    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'friend_vk_id', 'year', name='_user_friend_year_uc'),
    )

class FriendsHistory(Base):
    __tablename__ = "friends_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    friends_count = Column(Integer, nullable=False)

    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_friends_uc'),
        Index('ix_friends_history_user_date', 'user_id', 'date'),
    )





# --- START OF FILE backend/app/db/models/user.py ---

from datetime import datetime, UTC
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, Boolean, text, Enum, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.enums import DelayProfile, TeamMemberRole


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    vk_group_id = Column(BigInteger, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    photo_100 = Column(String)
    
    admin_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    admin = relationship("User", back_populates="managed_groups")

    encrypted_access_token = Column(String, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    vk_id = Column(BigInteger, unique=True, index=True, nullable=False)
    encrypted_vk_token = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    last_active_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(UTC), nullable=True, index=True)
    is_frozen = Column(Boolean, nullable=False, server_default='false')
    is_deleted = Column(Boolean, nullable=False, server_default='false', index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_shadow_banned = Column(Boolean, nullable=False, server_default='false', index=True)
    
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, nullable=False, server_default='false')
    daily_likes_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_add_friends_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_message_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_posts_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_join_groups_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_leave_groups_limit = Column(Integer, nullable=False, server_default=text('0'))
    delay_profile = Column(Enum(DelayProfile, native_enum=False), nullable=False, server_default=DelayProfile.normal.name)
    analytics_settings_posts_count = Column(Integer, nullable=False, server_default=text('100'))
    analytics_settings_photos_count = Column(Integer, nullable=False, server_default=text('200'))
    plan = relationship("Plan", back_populates="users", lazy="selectin")

    action_logs = relationship("ActionLog", back_populates="user", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="user", cascade="all, delete-orphan")
    daily_stats = relationship("DailyStats", back_populates="user", cascade="all, delete-orphan")
    filter_presets = relationship("FilterPreset", back_populates="user", cascade="all, delete-orphan")
    friend_requests = relationship("FriendRequestLog", back_populates="user", cascade="all, delete-orphan")
    heatmap = relationship("PostActivityHeatmap", back_populates="user", uselist=False, cascade="all, delete-orphan")
    login_history = relationship("LoginHistory", back_populates="user", cascade="all, delete-orphan", order_by="desc(LoginHistory.timestamp)")
    managed_profiles = relationship("ManagedProfile", foreign_keys="[ManagedProfile.manager_user_id]", back_populates="manager", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    owned_team = relationship("Team", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    profile_metrics = relationship("ProfileMetric", back_populates="user", cascade="all, delete-orphan")
    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan", lazy="select")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")
    scheduled_posts = relationship("ScheduledPost", back_populates="user", cascade="all, delete-orphan")
    task_history = relationship("TaskHistory", back_populates="user", cascade="all, delete-orphan")
    team_membership = relationship("TeamMember", back_populates="user", uselist=False, cascade="all, delete-orphan")
    managed_groups = relationship("Group", back_populates="admin", cascade="all, delete-orphan")

    ai_provider: Mapped[str | None] = mapped_column(String, nullable=True, comment="e.g., 'openai', 'google'")
    encrypted_ai_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_model_name: Mapped[str | None] = mapped_column(String, nullable=True, comment="e.g., 'gpt-4o', 'gemini-2.5-flash'")
    ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    role = Column(Enum(TeamMemberRole, native_enum=False), nullable=False, default=TeamMemberRole.member)
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_membership")
    profile_accesses = relationship("TeamProfileAccess", back_populates="team_member", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='_team_user_uc'),)

class TeamProfileAccess(Base):
    __tablename__ = "team_profile_access"
    id = Column(Integer, primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_member = relationship("TeamMember", back_populates="profile_accesses")
    profile = relationship("User", foreign_keys=[profile_user_id])
    __table_args__ = (UniqueConstraint('team_member_id', 'profile_user_id', name='_team_member_profile_uc'),)

class ManagedProfile(Base):
    __tablename__ = "managed_profiles"
    id = Column(Integer, primary_key=True)
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    manager = relationship("User", foreign_keys=[manager_user_id], back_populates="managed_profiles")
    profile = relationship("User", foreign_keys=[profile_user_id], backref="managed_by")
    __table_args__ = (UniqueConstraint('manager_user_id', 'profile_user_id', name='_manager_profile_uc'),)

class LoginHistory(Base):
    __tablename__ = "login_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    user = relationship("User", back_populates="login_history")
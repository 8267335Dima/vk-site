import datetime
import enum
from sqlalchemy import (
Column, Integer, String, DateTime, ForeignKey, BigInteger,
UniqueConstraint, Boolean, text, Enum, Text
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class DelayProfile(enum.Enum):
    slow = "slow"
    normal = "normal"
    fast = "fast"

class TeamMemberRole(enum.Enum):
    admin = "admin"
    member = "member"

class User(Base):
    tablename = "users"
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
    scheduled_posts = relationship("ScheduledPost", back_populates="user", cascade="all, delete-orphan", foreign_keys="[ScheduledPost.user_id]")
    owned_team = relationship("Team", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    team_membership = relationship("TeamMember", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Team(Base):
    tablename = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    owner = relationship("User", back_populates="owned_team")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

class TeamMember(Base):
    tablename = "team_members"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    role = Column(Enum(TeamMemberRole), nullable=False, default=TeamMemberRole.member)
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_membership")
    profile_accesses = relationship("TeamProfileAccess", back_populates="team_member", cascade="all, delete-orphan")
    table_args = (UniqueConstraint('team_id', 'user_id', name='_team_user_uc'),)

class TeamProfileAccess(Base):
    tablename = "team_profile_access"
    id = Column(Integer, primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_member = relationship("TeamMember", back_populates="profile_accesses")
    profile = relationship("User", foreign_keys=[profile_user_id])

class ManagedProfile(Base):
    tablename = "managed_profiles"
    id = Column(Integer, primary_key=True)
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    manager = relationship("User", foreign_keys=[manager_user_id], back_populates="managed_profiles")
    profile = relationship("User", foreign_keys=[profile_user_id])
    table_args = (UniqueConstraint('manager_user_id', 'profile_user_id', name='_manager_profile_uc'),)

class LoginHistory(Base):
    tablename = "login_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    user = relationship("User")
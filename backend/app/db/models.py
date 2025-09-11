# backend/app/db/models.py
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
    
    delay_profile = Column(Enum(DelayProfile), nullable=False, server_default=DelayProfile.normal.name)

    # Relationships
    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    task_history = relationship("TaskHistory", back_populates="user", cascade="all, delete-orphan")
    daily_stats = relationship("DailyStats", back_populates="user", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")
    profile_metrics = relationship("ProfileMetric", back_populates="user", cascade="all, delete-orphan")

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
    schedule = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    
    user = relationship("User", back_populates="scenarios")
    steps = relationship("ScenarioStep", back_populates="scenario", cascade="all, delete-orphan", lazy="selectin", order_by="ScenarioStep.step_order")

class ScenarioStep(Base):
    __tablename__ = "scenario_steps"
    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    action_type = Column(String, nullable=False)
    settings = Column(JSON, nullable=False)
    scenario = relationship("Scenario", back_populates="steps")

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
    week_identifier = Column(String, nullable=False)  # Например, '2024-35'
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
    month_identifier = Column(String, nullable=False) # Например, '2024-09'
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
    status = Column(String, nullable=False) # e.g., 'SUCCESS', 'ERROR'
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
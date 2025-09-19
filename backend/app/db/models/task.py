# backend/app/db/models/task.py

from datetime import datetime, UTC
import enum
from sqlalchemy import (
    Column, ForeignKeyConstraint, Integer, String, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, Boolean, JSON, Text, Enum, Index, Float
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.core.enums import ScenarioStepType, ScheduledPostStatus, AutomationType, ActionType, ActionStatus

class TaskHistory(Base):
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    arq_job_id = Column(String, unique=True, nullable=True, index=True)
    task_name = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING", nullable=False, index=True)
    parameters = Column(JSON, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    user = relationship("User", back_populates="task_history")
    __table_args__ = (Index('ix_task_history_user_status', 'user_id', 'status'),)

class Automation(Base):
    __tablename__ = "automations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_type = Column(Enum(AutomationType), nullable=False, index=True)
    is_active = Column(Boolean, default=False, nullable=False)
    settings = Column(JSON, nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="automations")
    __table_args__ = (UniqueConstraint('user_id', 'automation_type', name='_user_automation_uc'),)

class Scenario(Base):
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    schedule = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    
    first_step_id = Column(Integer, nullable=True)

    user = relationship("User", back_populates="scenarios")
    steps = relationship(
        "ScenarioStep", 
        back_populates="scenario", 
        cascade="all, delete-orphan", 
        foreign_keys="[ScenarioStep.scenario_id]"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['first_step_id'], 
            ['scenario_steps.id'],
            use_alter=True, 
            name="fk_scenarios_first_step_id_scenario_steps"
        ),
    )

class ScenarioStep(Base):
    __tablename__ = "scenario_steps"
    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    step_type = Column(Enum(ScenarioStepType), nullable=False)
    details = Column(JSON, nullable=False)
    next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True)
    on_success_next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True)
    on_failure_next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True)
    position_x = Column(Float, default=0)
    position_y = Column(Float, default=0)
    scenario = relationship("Scenario", back_populates="steps", foreign_keys=[scenario_id])

class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vk_profile_id = Column(BigInteger, nullable=False, index=True)
    post_text = Column(Text, nullable=True)
    attachments = Column(JSON, nullable=True)
    publish_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(ScheduledPostStatus), nullable=False, default=ScheduledPostStatus.scheduled, index=True)
    arq_job_id = Column(String, nullable=True, unique=True)
    vk_post_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    user = relationship("User", back_populates="scheduled_posts")

class SentCongratulation(Base):
    __tablename__ = "sent_congratulations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_vk_id = Column(BigInteger, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    user = relationship("User")
    __table_args__ = (UniqueConstraint('user_id', 'friend_vk_id', 'year', name='_user_friend_year_uc'),)

class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(Enum(ActionType), nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(Enum(ActionStatus), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    user = relationship("User", back_populates="action_logs")
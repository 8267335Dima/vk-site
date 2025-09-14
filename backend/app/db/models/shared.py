# РЕФАКТОРИНГ: Общие модели, которые используются в разных частях системы.

import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    UniqueConstraint, Boolean, JSON,
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_proxy_url = Column(String, nullable=False)
    is_working = Column(Boolean, default=True, nullable=False, index=True)
    last_checked_at = Column(DateTime, default=datetime.datetime.utcnow)
    check_status_message = Column(String, nullable=True)
    user = relationship("User", back_populates="proxies")
    __table_args__ = (UniqueConstraint('user_id', 'encrypted_proxy_url', name='_user_proxy_uc'),)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String, nullable=False)
    level = Column(String, default="info", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    user = relationship("User", back_populates="notifications")

class FilterPreset(Base):
    __tablename__ = "filter_presets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    action_type = Column(String, nullable=False, index=True)
    filters = Column(JSON, nullable=False)
    user = relationship("User", back_populates="filter_presets")
    __table_args__ = (UniqueConstraint('user_id', 'name', 'action_type', name='_user_name_action_uc'),)

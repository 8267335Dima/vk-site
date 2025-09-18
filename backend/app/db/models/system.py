# backend/app/db/models/system.py
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base

class GlobalSetting(Base):
    """Модель для хранения глобальных настроек ключ-значение."""
    __tablename__ = "global_settings"
    key = Column(String, primary_key=True, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)

class BannedIP(Base):
    """Модель для хранения заблокированных IP-адресов."""
    __tablename__ = "banned_ips"
    id = Column(Integer, primary_key=True)
    ip_address = Column(String, unique=True, index=True, nullable=False)
    reason = Column(String, nullable=True)
    banned_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    admin = relationship("User")
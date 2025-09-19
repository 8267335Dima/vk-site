# backend/app/db/models/payment.py
from datetime import datetime, UTC
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Enum, JSON, Boolean, Text
from sqlalchemy.orm import relationship
from app.db.base import Base

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    name_id = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    base_price = Column(Float, nullable=True)
    limits = Column(JSON, nullable=False)
    available_features = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_popular = Column(Boolean, default=False)
    
    users = relationship("User", back_populates="plan")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    payment_system_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus, native_enum=False), default=PaymentStatus.PENDING, nullable=False)
    plan_name = Column(String, nullable=False)
    months = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    error_message = Column(Text, nullable=True)
    user = relationship("User")
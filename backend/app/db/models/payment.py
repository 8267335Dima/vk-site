# backend/app/db/models/payment.py

import datetime
# --- НАЧАЛО ИСПРАВЛЕНИЯ ---
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Enum
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---
from sqlalchemy.orm import relationship
from app.db.base import Base

# --- НАЧАЛО ИСПРАВЛЕНИЯ: Добавлено отсутствующее перечисление ---
class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    payment_system_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    plan_name = Column(String, nullable=False)
    months = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = relationship("User")
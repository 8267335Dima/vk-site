# backend/app/api/schemas/billing.py
from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class PlanDetail(BaseModel):
    """Детальная информация о тарифном плане для отображения на фронтенде."""
    id: str = Field(..., description="Идентификатор плана (напр., 'Plus', 'PRO')")
    display_name: str = Field(..., description="Человекочитаемое название тарифа")
    price: float = Field(..., description="Цена тарифа")
    currency: str = Field(..., description="Валюта")
    description: str = Field(..., description="Описание тарифа")
    # --- ИСПРАВЛЕНИЕ: Добавлены новые поля ---
    features: List[str] = Field([], description="Список возможностей тарифа")
    is_popular: Optional[bool] = Field(False, description="Является ли тариф популярным выбором")


class AvailablePlansResponse(BaseModel):
    """Ответ со списком доступных для покупки планов."""
    plans: List[PlanDetail]

class CreatePaymentRequest(BaseModel):
    plan_name: str = Field(..., description="Идентификатор тарифа для покупки (напр., 'Plus')")

class CreatePaymentResponse(BaseModel):
    confirmation_url: str
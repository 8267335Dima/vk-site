# --- backend/app/api/schemas/billing.py ---
from pydantic import BaseModel, Field
from typing import List, Optional

class PlanPeriod(BaseModel):
    """Схема для описания периода подписки и скидки."""
    months: int
    discount_percent: float

class PlanDetail(BaseModel):
    """Детальная информация о тарифном плане для отображения на фронтенде."""
    id: str = Field(..., description="Идентификатор плана (напр., 'Plus', 'PRO')")
    display_name: str = Field(..., description="Человекочитаемое название тарифа")
    price: float = Field(..., description="Цена тарифа за 1 месяц")
    currency: str = Field("RUB", description="Валюта")
    description: str = Field(..., description="Описание тарифа")
    features: List[str] = Field([], description="Список возможностей тарифа")
    is_popular: Optional[bool] = Field(False, description="Является ли тариф популярным выбором")
    periods: List[PlanPeriod] = Field([], description="Доступные периоды подписки со скидками")

class AvailablePlansResponse(BaseModel):
    """Ответ со списком доступных для покупки планов."""
    plans: List[PlanDetail]

class CreatePaymentRequest(BaseModel):
    """
    Схема для создания платежа.
    ИСПРАВЛЕНО: Поля plan_id и months соответствуют логике эндпоинта.
    """
    plan_id: str = Field(..., description="Идентификатор тарифа для покупки (напр., 'Plus')")
    months: int = Field(..., ge=1, description="Количество месяцев для покупки")

class CreatePaymentResponse(BaseModel):
    confirmation_url: str
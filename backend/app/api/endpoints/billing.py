# backend/app/api/endpoints/billing.py
import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi_cache.decorator import cache

from app.db.session import get_db
from app.db.models import User, Payment
from app.api.dependencies import get_current_user
from app.api.schemas.billing import CreatePaymentRequest, CreatePaymentResponse, AvailablePlansResponse, PlanDetail
from app.core.config import settings
from app.core.config_loader import PLAN_CONFIG
import structlog

from app.core.plans import get_limits_for_plan 

log = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/plans", response_model=AvailablePlansResponse)
@cache(expire=3600)
async def get_available_plans():
    """
    Возвращает список всех доступных для покупки тарифных планов.
    """
    available_plans = []
    for plan_id, config in PLAN_CONFIG.items():
        # --- ИСПРАВЛЕНИЕ: Отдаем все поля, включая features ---
        if "price" in config:
            available_plans.append(PlanDetail(
                id=plan_id,
                display_name=config.get("display_name", plan_id),
                price=config["price"],
                currency=config.get("currency", "RUB"),
                description=config.get("description", ""),
                features=config.get("features", []),
                is_popular=config.get("isPopular", False)
            ))
    return AvailablePlansResponse(plans=available_plans)


@router.post("/create-payment", response_model=CreatePaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Создает платеж, используя цены из централизованной конфигурации.
    """
    plan_name = request.plan_name
    plan_info = PLAN_CONFIG.get(plan_name)

    if not plan_info or "price" not in plan_info:
        raise HTTPException(status_code=400, detail="Неверное название тарифа или тариф не является платным.")

    amount = plan_info["price"]
    

    idempotency_key = str(uuid.uuid4())
    payment_response = {
        "id": f"test_payment_{uuid.uuid4()}",
        "status": "pending",
        "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=2d12b192-000f-5000-9000-1121d5a37213" # Пример ссылки
    }
    
    new_payment = Payment(
        payment_system_id=payment_response["id"],
        user_id=current_user.id,
        amount=amount,
        status=payment_response["status"],
        plan_name=plan_name
    )
    db.add(new_payment)
    await db.commit()

    log.info("payment.created", user_id=current_user.id, plan=plan_name, payment_id=new_payment.id)

    return CreatePaymentResponse(confirmation_url=payment_response["confirmation_url"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Обрабатывает вебхуки от платежной системы.
    """
    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    if event.get("event") == "payment.succeeded":
        payment_data = event.get("object", {})
        payment_system_id = payment_data.get("id")
        
        if not payment_system_id:
            return {"status": "error", "message": "Payment ID missing."}

        query = select(Payment).where(Payment.payment_system_id == payment_system_id)
        result = await db.execute(query)
        payment = result.scalar_one_or_none()

        if not payment or payment.status == "succeeded":
            return {"status": "ok"}
            
        plan_info = PLAN_CONFIG.get(payment.plan_name)
        received_amount = float(payment_data.get("amount", {}).get("value", 0))
        
        if not plan_info or "price" not in plan_info or received_amount != plan_info["price"]:
            payment.status = "failed"
            await db.commit()
            log.error("webhook.amount_mismatch", payment_id=payment.id, expected=plan_info.get('price'), got=received_amount)
            return {"status": "ok"}

        user = await db.get(User, payment.user_id)
        if not user:
            log.error("webhook.user_not_found", user_id=payment.user_id)
            return {"status": "ok"}

        start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > datetime.datetime.utcnow() else datetime.datetime.utcnow()
        
        user.plan = payment.plan_name
        user.plan_expires_at = start_date + datetime.timedelta(days=30)
        
        new_limits = get_limits_for_plan(user.plan)
        user.daily_likes_limit = new_limits.get("daily_likes_limit", 0)
        user.daily_add_friends_limit = new_limits.get("daily_add_friends_limit", 0)

        payment.status = "succeeded"
        
        await db.commit()
        log.info("webhook.success", user_id=user.id, plan=user.plan, expires_at=user.plan_expires_at)

    return {"status": "ok"}
# backend/app/api/endpoints/billing.py
import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi_cache.decorator import cache

from app.db.session import get_db
from app.db.models import User, Payment
from app.api.dependencies import get_current_active_profile
from app.api.schemas.billing import CreatePaymentRequest, CreatePaymentResponse, AvailablePlansResponse, PlanDetail
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
        if config.base_price is not None:
            available_plans.append({
                "id": plan_id,
                "display_name": config.display_name,
                "price": config.base_price, 
                "currency": "RUB", # Можно вынести в конфиг
                "description": config.description,
                "features": config.features,
                "is_popular": config.is_popular,
                "periods": [p.model_dump() for p in config.periods]
            })
    return {"plans": available_plans}


@router.post("/create-payment", response_model=CreatePaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Создает платеж, используя цены из централизованной конфигурации.
    """
    plan_id = request.plan_id
    months = request.months
    plan_info = PLAN_CONFIG.get(plan_id)

    if not plan_info or plan_info.base_price is None:
        raise HTTPException(status_code=400, detail="Неверное название тарифа или тариф не является платным.")

    base_price = plan_info.base_price
    final_price = base_price * months

    period_info = next((p for p in plan_info.periods if p.months == months), None)
    if period_info:
        final_price *= (1 - period_info.discount_percent / 100)
    
    final_price = round(final_price, 2)

    idempotency_key = str(uuid.uuid4())
    # Здесь должна быть реальная интеграция с YooKassa
    payment_response = {
        "id": f"test_payment_{uuid.uuid4()}",
        "status": "pending",
        "amount": {"value": str(final_price), "currency": "RUB"},
        "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=2d12b192-000f-5000-9000-1121d5a37213"}
    }
    
    new_payment = Payment(
        payment_system_id=payment_response["id"],
        user_id=current_user.id,
        amount=final_price,
        status=payment_response["status"],
        plan_name=plan_id,
        months=months
    )
    db.add(new_payment)
    await db.commit()

    log.info("payment.created", user_id=current_user.id, plan=plan_id, payment_id=new_payment.id, amount=final_price)

    return CreatePaymentResponse(confirmation_url=payment_response["confirmation"]["confirmation_url"])


@router.post("/webhook", status_code=status.HTTP_200_OK, include_in_schema=False)
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Обрабатывает вебхуки от платежной системы.
    ВНИМАНИЕ: В production-среде необходимо добавить проверку IP-адреса
    или подписи запроса от YooKassa для безопасности.
    """
    try:
        event = await request.json()
    except Exception:
        log.warn("webhook.invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    # ВАЖНО: Проверка подписи от YooKassa должна быть здесь
    # signature = request.headers.get('Yoo-Kassa-Signature')
    # if not is_valid_signature(event, signature):
    #     log.error("webhook.invalid_signature")
    #     raise HTTPException(status_code=403, detail="Invalid signature")

    event_type = event.get("event")
    payment_data = event.get("object", {})
    payment_system_id = payment_data.get("id")
    
    log.info("webhook.received", event_type=event_type, payment_id=payment_system_id)
    
    if event_type == "payment.succeeded":
        if not payment_system_id:
            return {"status": "error", "message": "Payment ID missing."}

        async with db.begin():
            query = select(Payment).where(Payment.payment_system_id == payment_system_id)
            payment = (await db.execute(query)).scalar_one_or_none()

            if not payment:
                log.warn("webhook.payment_not_found", payment_id=payment_system_id)
                return {"status": "ok"} # Возвращаем 200, чтобы система не повторяла запрос

            if payment.status == "succeeded":
                log.info("webhook.already_processed", payment_id=payment.id)
                return {"status": "ok"}
            
            user = await db.get(User, payment.user_id, with_for_update=True)
            if not user:
                log.error("webhook.user_not_found", user_id=payment.user_id)
                return {"status": "ok"} 

            received_amount = float(payment_data.get("amount", {}).get("value", 0))
            if abs(received_amount - payment.amount) > 0.01:
                payment.status = "failed"
                log.error("webhook.amount_mismatch", payment_id=payment.id, expected=payment.amount, got=received_amount)
                return {"status": "ok"}

            start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > datetime.datetime.utcnow() else datetime.datetime.utcnow()
            
            user.plan = payment.plan_name
            user.plan_expires_at = start_date + datetime.timedelta(days=30 * payment.months)
            
            new_limits = get_limits_for_plan(user.plan)
            user.daily_likes_limit = new_limits.get("daily_likes_limit", 0)
            user.daily_add_friends_limit = new_limits.get("daily_add_friends_limit", 0)

            payment.status = "succeeded"
            
            log.info("webhook.success", user_id=user.id, plan=user.plan, expires_at=user.plan_expires_at)
            
    return {"status": "ok"}
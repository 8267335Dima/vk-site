# --- START OF FILE backend/app/api/endpoints/billing.py ---

from datetime import datetime, UTC
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError # <-- ВОТ ИСПРАВЛЕНИЕ
from fastapi_cache.decorator import cache

from app.db.session import get_db
from app.db.models import User, Payment, Plan
from app.api.dependencies import check_etag, get_current_active_profile
from app.api.schemas.billing import CreatePaymentRequest, CreatePaymentResponse, AvailablePlansResponse, PlanDetail
from app.core.config_loader import PLAN_CONFIG
import structlog


log = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/plans", response_model=AvailablePlansResponse)
@cache(expire=3600)
async def get_available_plans(request: Request, response: Response):
    available_plans = []
    for plan_id, config in PLAN_CONFIG.items():
        if config.base_price is not None:
            available_plans.append({
                "id": plan_id,
                "display_name": config.display_name,
                "price": config.base_price, 
                "currency": "RUB",
                "description": config.description,
                "features": config.features,
                "is_popular": config.is_popular,
                "periods": [p.model_dump() for p in config.periods]
            })
    plans_response_model = AvailablePlansResponse(plans=available_plans)
    json_response = ORJSONResponse(plans_response_model.model_dump(by_alias=True))
    await check_etag(request, response, json_response.body)
    return plans_response_model


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
    if months > 1 and not period_info:
        allowed_periods = ", ".join(str(p.months) for p in plan_info.periods)
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимый период подписки. Доступные периоды (в месяцах): 1, {allowed_periods}"
        )

        
    if period_info:
        final_price *= (1 - period_info.discount_percent / 100)
    
    final_price = round(final_price, 2)

    payment_response = {
        "id": f"test_payment_{uuid.uuid4()}",
        "status": "pending",
        "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=fake-order-id"}
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
    try:
        event = await request.json()
        idempotency_key = request.headers.get("Idempotence-Key")
    except Exception:
        log.warn("webhook.invalid_json_or_key")
        raise HTTPException(status_code=400, detail="Invalid JSON or missing Idempotence-Key.")
    event_type = event.get("event")
    payment_data = event.get("object", {})
    payment_system_id = payment_data.get("id")
    log.info("webhook.received", event_type=event_type, payment_id=payment_system_id)
    if event_type == "payment.succeeded":
        if not payment_system_id:
            return {"status": "error", "message": "Payment ID missing."}
        query = select(Payment).where(Payment.payment_system_id == payment_system_id).with_for_update()
        payment = (await db.execute(query)).scalar_one_or_none()
        if not payment:
            log.warn("webhook.payment_not_found", payment_id=payment_system_id)
            return {"status": "ok"}
        if payment.status == "succeeded":
            log.info("webhook.already_processed", payment_id=payment.id)
            return {"status": "ok"}
        payment.idempotency_key = idempotency_key
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            log.warn("webhook.duplicate_idempotency_key", key=idempotency_key)
            return {"status": "ok"}
        user = await db.get(User, payment.user_id, with_for_update=True)
        if not user:
            log.error("webhook.user_not_found", user_id=payment.user_id)
            payment.status = "failed"
            payment.error_message = "User not found"
            await db.commit()
            return {"status": "ok"}
        received_amount = float(payment_data.get("amount", {}).get("value", 0))
        if abs(received_amount - payment.amount) > 0.01:
            payment.status = "failed"
            payment.error_message = f"Amount mismatch: expected {payment.amount}, got {received_amount}"
            log.error("webhook.amount_mismatch", payment_id=payment.id, expected=payment.amount, got=received_amount)
            await db.commit()
            return {"status": "ok"}
        new_plan_stmt = select(Plan).where(Plan.name_id == payment.plan_name)
        new_plan = (await db.execute(new_plan_stmt)).scalar_one_or_none()
        if not new_plan:
            log.error("webhook.plan_not_found", payment_id=payment.id, plan_name=payment.plan_name)
            payment.status = "failed"
            payment.error_message = f"Plan '{payment.plan_name}' not found."
            await db.commit()
            return {"status": "ok"}
        start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > datetime.datetime.now(datetime.UTC) else datetime.datetime.now(datetime.UTC)
        user.plan_id = new_plan.id
        user.plan_expires_at = start_date + datetime.timedelta(days=30 * payment.months)
        new_limits = new_plan.limits
        for key, value in new_limits.items():
            if hasattr(user, key):
                setattr(user, key, value)
        payment.status = "succeeded"
        log.info("webhook.success", user_id=user.id, plan=new_plan.name_id, expires_at=user.plan_expires_at)
        await db.commit()
    return {"status": "ok"}
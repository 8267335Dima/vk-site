from datetime import timedelta, datetime, UTC
from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.models import User, LoginHistory, Plan
from app.api.schemas.auth import EnrichedTokenResponse
from app.services.vk_api import is_token_valid
from app.core.security import create_access_token, encrypt_data
from app.core.config import settings
from app.core.plans import get_limits_for_plan
from app.core.enums import PlanName
from app.api.dependencies import get_arq_pool, get_current_manager_user, limiter
from app.db.models.task import TaskHistory

router = APIRouter()

class TokenRequest(BaseModel):
    vk_token: str


@router.post(
    "/vk",
    response_model=EnrichedTokenResponse,
    summary="Аутентификация или регистрация по токену VK",
    dependencies=[Depends(limiter)]
)
async def login_via_vk(
    *,
    request: Request,
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
    token_request: TokenRequest
) -> EnrichedTokenResponse:
    vk_token = token_request.vk_token
    vk_id = await is_token_valid(vk_token)
    if not vk_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный или просроченный токен VK.")
    query = select(User).where(User.vk_id == vk_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    encrypted_token = encrypt_data(vk_token)
    is_new_user = False
    if user:
        user.encrypted_vk_token = encrypted_token
    else:
        is_new_user = True
        base_plan_stmt = select(Plan).where(Plan.name_id == PlanName.BASE.name)
        base_plan = (await db.execute(base_plan_stmt)).scalar_one_or_none()
        if not base_plan:
            raise HTTPException(status_code=500, detail="Базовый тарифный план не найден в системе.")
        user_data = {
            "vk_id": vk_id,
            "encrypted_vk_token": encrypted_token,
            "plan_id": base_plan.id,
            "plan_expires_at": datetime.now(UTC) + timedelta(days=14),
        }
        user_model_columns = {c.name for c in User.__table__.columns}
        valid_limits_for_db = {
            key: value for key, value in base_plan.limits.items() if key in user_model_columns
        }
        user_data.update(valid_limits_for_db)
        user = User(**user_data)
        db.add(user)
    if str(vk_id) == settings.ADMIN_VK_ID:
        admin_plan_stmt = select(Plan).where(Plan.name_id == PlanName.PRO.name)
        admin_plan = (await db.execute(admin_plan_stmt)).scalar_one_or_none()
        if not admin_plan:
             raise HTTPException(status_code=500, detail="PRO тарифный план не найден в системе.")
        user.is_admin = True
        user.plan_id = admin_plan.id
        user.plan_expires_at = None
        user_model_columns = {c.name for c in User.__table__.columns}
        for key, value in admin_plan.limits.items():
            if key in user_model_columns:
                setattr(user, key, value)
    await db.commit()
    if is_new_user:
        demo_task_history = TaskHistory(
            user_id=user.id, task_name="Просмотр историй", status="PENDING",
            parameters={"count": 5}
        )
        db.add(demo_task_history)
        await db.flush()
        job = await arq_pool.enqueue_job(
            "view_stories_task", task_history_id=demo_task_history.id, _queue_name='high_priority'
        )
        demo_task_history.arq_job_id = job.job_id
        await db.commit()
    login_entry = LoginHistory(
        user_id=user.id,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown")
    )
    db.add(login_entry)
    await db.commit()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": str(user.id), "profile_id": str(user.id)}
    access_token = create_access_token(data=token_data, expires_delta=access_token_expires)
    return EnrichedTokenResponse(
        access_token=access_token, token_type="bearer",
        manager_id=user.id, active_profile_id=user.id
    )


class SwitchProfileRequest(BaseModel):
    profile_id: int

@router.post("/switch-profile", response_model=EnrichedTokenResponse, summary="Переключиться на другой управляемый профиль")
async def switch_profile(
    request_data: SwitchProfileRequest,
    manager: User = Depends(get_current_manager_user),
    db: AsyncSession = Depends(get_db)
) -> EnrichedTokenResponse:
    
    await db.refresh(manager, attribute_names=["managed_profiles", "team_membership"])
    if manager.team_membership:
        await db.refresh(manager.team_membership, attribute_names=["profile_accesses"])

    allowed_profile_ids = {manager.id}

    if manager.managed_profiles:
        allowed_profile_ids.update({p.profile_user_id for p in manager.managed_profiles})

    if manager.team_membership and manager.team_membership.profile_accesses:
        allowed_profile_ids.update({p.profile_user_id for p in manager.team_membership.profile_accesses})

    if request_data.profile_id not in allowed_profile_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к этому профилю запрещен.")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": str(manager.id),
        "profile_id": str(request_data.profile_id)
    }
    
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    return EnrichedTokenResponse(
        access_token=access_token, 
        token_type="bearer",
        manager_id=manager.id,
        active_profile_id=request_data.profile_id
    )
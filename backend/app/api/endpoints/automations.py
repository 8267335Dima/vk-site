# backend/app/api/endpoints/automations.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import User, Automation
from app.api.dependencies import get_current_user
from app.core.config_loader import AUTOMATIONS_CONFIG
# --- НОВЫЙ ИМПОРТ ---
from app.core.plans import is_automation_available_for_plan

router = APIRouter()

class AutomationStatus(BaseModel):
    automation_type: str
    is_active: bool
    settings: Dict[str, Any] | None = None
    name: str
    description: str
    is_available: bool # <-- НОВОЕ ПОЛЕ для UI

class AutomationUpdateRequest(BaseModel):
    is_active: bool
    settings: Dict[str, Any] | None = None

@router.get("", response_model=List[AutomationStatus])
async def get_automations_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает статусы всех автоматизаций, указывая, доступны ли они по тарифу."""
    query = select(Automation).where(Automation.user_id == current_user.id)
    result = await db.execute(query)
    user_automations_db = {auto.automation_type: auto for auto in result.scalars().all()}
    
    response_list = []
    for config_item in AUTOMATIONS_CONFIG:
        auto_type = config_item['id']
        db_item = user_automations_db.get(auto_type)
        
        # Проверяем доступность функции для текущего плана пользователя
        is_available = is_automation_available_for_plan(current_user.plan, auto_type)
        
        response_list.append(AutomationStatus(
            automation_type=auto_type,
            is_active=db_item.is_active if db_item else False,
            settings=db_item.settings if db_item else {},
            name=config_item['name'],
            description=config_item['description'],
            is_available=is_available
        ))
        
    return response_list

@router.post("/{automation_type}", response_model=AutomationStatus)
async def update_automation(
    automation_type: str,
    request_data: AutomationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Включает, выключает или настраивает автоматизацию с проверкой прав доступа."""
    # --- ПРОВЕРКА ПРАВ ДОСТУПА ---
    if request_data.is_active and not is_automation_available_for_plan(current_user.plan, automation_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Функция '{automation_type}' недоступна на вашем тарифе '{current_user.plan}'."
        )

    config_item = next((item for item in AUTOMATIONS_CONFIG if item['id'] == automation_type), None)
    if not config_item:
        raise HTTPException(status_code=404, detail="Автоматизация такого типа не найдена.")

    query = select(Automation).where(
        Automation.user_id == current_user.id,
        Automation.automation_type == automation_type
    )
    result = await db.execute(query)
    automation = result.scalar_one_or_none()

    if not automation:
        automation = Automation(
            user_id=current_user.id,
            automation_type=automation_type,
            is_active=request_data.is_active,
            settings=request_data.settings
        )
        db.add(automation)
    else:
        automation.is_active = request_data.is_active
        if request_data.settings is not None:
            if automation.settings is None:
                automation.settings = {}
            automation.settings.update(request_data.settings)
    
    await db.commit()
    await db.refresh(automation)
    
    return AutomationStatus(
        automation_type=automation.automation_type,
        is_active=automation.is_active,
        settings=automation.settings,
        name=config_item['name'],
        description=config_item['description'],
        is_available=True # Если мы дошли сюда, значит она доступна
    )
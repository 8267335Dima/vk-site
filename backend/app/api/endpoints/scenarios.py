# backend/app/api/endpoints/scenarios.py
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from croniter import croniter
from app.db.session import get_db
from app.db.models import User, Scenario, ScenarioStep
from app.api.dependencies import get_current_user
from app.api.schemas.scenarios import Scenario as ScenarioSchema, ScenarioCreate, ScenarioUpdate
from sqlalchemy_celery_beat.models import PeriodicTask, CrontabSchedule
from app.tasks.runner import run_scenario_from_scheduler

router = APIRouter()

async def _create_or_update_periodic_task(db: AsyncSession, scenario: Scenario):
    task_name = f"scenario-{scenario.id}"

    stmt = select(PeriodicTask).where(PeriodicTask.name == task_name)
    result = await db.execute(stmt)
    periodic_task = result.scalar_one_or_none()

    if not scenario.is_active:
        if periodic_task:
            periodic_task.enabled = False
        return

    try:
        minute, hour, day, week, month = scenario.schedule.split(' ')
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    crontab_stmt = select(CrontabSchedule).where(
        CrontabSchedule.minute == minute, CrontabSchedule.hour == hour,
        CrontabSchedule.day_of_month == day, CrontabSchedule.day_of_week == week,
        CrontabSchedule.month_of_year == month
    )
    res = await db.execute(crontab_stmt)
    crontab = res.scalar_one_or_none()
    if not crontab:
        crontab = CrontabSchedule(
            minute=minute, hour=hour, day_of_month=day,
            day_of_week=week, month_of_year=month
        )
        db.add(crontab)
        await db.flush()

    task_args = json.dumps([scenario.id])

    if periodic_task:
        periodic_task.crontab = crontab
        periodic_task.args = task_args
        periodic_task.enabled = True
    else:
        new_task = PeriodicTask(
            name=task_name,
            task=run_scenario_from_scheduler.name,
            crontab=crontab,
            args=task_args,
            enabled=True
        )
        db.add(new_task)

@router.get("", response_model=List[ScenarioSchema])
async def get_user_scenarios(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.user_id == current_user.id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=ScenarioSchema, status_code=status.HTTP_201_CREATED)
async def create_scenario(scenario_data: ScenarioCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    new_scenario = Scenario(user_id=current_user.id, name=scenario_data.name, schedule=scenario_data.schedule, is_active=scenario_data.is_active)
    db.add(new_scenario)
    await db.flush()

    new_steps = [ScenarioStep(scenario_id=new_scenario.id, **step.model_dump()) for step in scenario_data.steps]
    db.add_all(new_steps)
    
    await _create_or_update_periodic_task(db, new_scenario)
    await db.commit()
    await db.refresh(new_scenario)
    return new_scenario

@router.put("/{scenario_id}", response_model=ScenarioSchema)
async def update_scenario(scenario_id: int, scenario_data: ScenarioUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    db_scenario.name = scenario_data.name
    db_scenario.schedule = scenario_data.schedule
    db_scenario.is_active = scenario_data.is_active
    
    for step in db_scenario.steps:
        await db.delete(step)
    await db.flush()

    new_steps = [ScenarioStep(scenario_id=db_scenario.id, **step.model_dump()) for step in scenario_data.steps]
    db.add_all(new_steps)
    
    await _create_or_update_periodic_task(db, db_scenario)
    await db.commit()
    await db.refresh(db_scenario)
    return db_scenario

@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(scenario_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    
    task_name = f"scenario-{db_scenario.id}"
    stmt_task = select(PeriodicTask).where(PeriodicTask.name == task_name)
    res_task = await db.execute(stmt_task)
    periodic_task = res_task.scalar_one_or_none()
    if periodic_task:
        await db.delete(periodic_task)
    
    await db.delete(db_scenario)
    await db.commit()
# --- backend/app/api/endpoints/scenarios.py ---
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from croniter import croniter

from app.db.session import get_db
from app.db.models import User, Scenario, ScenarioStep
from app.api.dependencies import get_current_active_profile
from app.api.schemas.scenarios import (
    Scenario as ScenarioSchema, ScenarioCreate, ScenarioUpdate, AvailableCondition,
    ConditionOption, ScenarioStepNode, ScenarioEdge
)
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

    minute, hour, day_of_month, month_of_year, day_of_week = scenario.schedule.split(' ')

    crontab_stmt = select(CrontabSchedule).where(
        CrontabSchedule.minute == minute, CrontabSchedule.hour == hour,
        CrontabSchedule.day_of_month == day_of_month, CrontabSchedule.day_of_week == day_of_week,
        CrontabSchedule.month_of_year == month_of_year
    )
    res = await db.execute(crontab_stmt)
    crontab = res.scalar_one_or_none()
    if not crontab:
        crontab = CrontabSchedule(
            minute=minute, hour=hour, day_of_month=day_of_month,
            day_of_week=day_of_week, month_of_year=month_of_year
        )
        db.add(crontab)
        await db.flush()

    task_args = json.dumps([scenario.id, scenario.user_id])

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

@router.get("/available-conditions", response_model=List[AvailableCondition])
async def get_available_conditions():
    return [
        {
            "key": "friends_count", "label": "Количество друзей", "type": "number",
            "operators": ["==", "!=", ">", "<", ">=", "<="]
        },
        {
            "key": "conversion_rate", "label": "Конверсия заявок (%)", "type": "number",
            "operators": [">", "<", ">=", "<="]
        },
        {
            "key": "day_of_week", "label": "День недели", "type": "select", "operators": ["==", "!="],
            "options": [
                {"value": "1", "label": "Понедельник"}, {"value": "2", "label": "Вторник"},
                {"value": "3", "label": "Среда"}, {"value": "4", "label": "Четверг"},
                {"value": "5", "label": "Пятница"}, {"value": "6", "label": "Суббота"},
                {"value": "7", "label": "Воскресенье"},
            ]
        }
    ]

def _db_to_graph(scenario: Scenario) -> tuple[List[ScenarioStepNode], List[ScenarioEdge]]:
    nodes = []
    edges = []
    if not scenario.steps:
        return nodes, edges
    
    # Создаем временное отображение ID из БД на frontend ID (который хранится в details)
    db_id_to_frontend_id = {step.id: str(step.details.get('id', step.id)) for step in scenario.steps}

    for step in scenario.steps:
        node_id_str = db_id_to_frontend_id[step.id]
        node_type = step.step_type.value
        
        # Особый случай для узла "Старт"
        if node_type == 'action' and step.details.get('action_type') == 'start':
            node_type = 'start'

        nodes.append(ScenarioStepNode(
            id=node_id_str,
            type=node_type,
            data=step.details.get('data', {}),
            position={"x": step.position_x, "y": step.position_y}
        ))
        
        source_id_str = db_id_to_frontend_id[step.id]
        if step.next_step_id and step.next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.next_step_id]
            edges.append(ScenarioEdge(id=f"e{source_id_str}-{target_id_str}", source=source_id_str, target=target_id_str))
        if step.on_success_next_step_id and step.on_success_next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.on_success_next_step_id]
            edges.append(ScenarioEdge(id=f"e{source_id_str}-{target_id_str}-success", source=source_id_str, target=target_id_str, sourceHandle='on_success'))
        if step.on_failure_next_step_id and step.on_failure_next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.on_failure_next_step_id]
            edges.append(ScenarioEdge(id=f"e{source_id_str}-{target_id_str}-failure", source=source_id_str, target=str(target_id_str), sourceHandle='on_failure'))

    return nodes, edges

async def _graph_to_db(db: AsyncSession, scenario: Scenario, data: ScenarioCreate):
    # Удаляем старые шаги, если они есть
    if scenario.steps:
        for step in scenario.steps:
            await db.delete(step)
        await db.flush()

    node_map = {}  # {frontend_id: db_step_object}
    start_node_frontend_id = None

    for node_data in data.nodes:
        step_type = node_data.type
        details_data = {'id': node_data.id, 'data': node_data.data}
        
        if node_data.type == 'start':
            step_type = 'action'
            details_data['action_type'] = 'start'
            start_node_frontend_id = node_data.id

        new_step = ScenarioStep(
            scenario_id=scenario.id,
            step_type=step_type,
            details=details_data,
            position_x=node_data.position.get('x', 0),
            position_y=node_data.position.get('y', 0)
        )
        db.add(new_step)
        await db.flush()
        node_map[node_data.id] = new_step
    
    for edge_data in data.edges:
        source_node = node_map.get(edge_data.source)
        target_node = node_map.get(edge_data.target)
        if not source_node or not target_node: continue

        if source_node.step_type.value == 'action':
            source_node.next_step_id = target_node.id
        elif source_node.step_type.value == 'condition':
            if edge_data.sourceHandle == 'on_success':
                source_node.on_success_next_step_id = target_node.id
            elif edge_data.sourceHandle == 'on_failure':
                source_node.on_failure_next_step_id = target_node.id

    if start_node_frontend_id:
        start_step_db = node_map.get(start_node_frontend_id)
        if start_step_db:
            scenario.first_step_id = start_step_db.id

@router.get("", response_model=List[ScenarioSchema])
async def get_user_scenarios(current_user: User = Depends(get_current_active_profile), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.user_id == current_user.id).options(selectinload(Scenario.steps))
    result = await db.execute(stmt)
    scenarios_db = result.scalars().unique().all()
    
    response_list = []
    for s in scenarios_db:
        nodes, edges = _db_to_graph(s)
        response_list.append(ScenarioSchema(id=s.id, name=s.name, schedule=s.schedule, is_active=s.is_active, nodes=nodes, edges=edges))
    return response_list

@router.get("/{scenario_id}", response_model=ScenarioSchema)
async def get_scenario(scenario_id: int, current_user: User = Depends(get_current_active_profile), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == current_user.id).options(selectinload(Scenario.steps))
    result = await db.execute(stmt)
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    
    nodes, edges = _db_to_graph(scenario)
    return ScenarioSchema(id=scenario.id, name=scenario.name, schedule=scenario.schedule, is_active=scenario.is_active, nodes=nodes, edges=edges)

@router.post("", response_model=ScenarioSchema, status_code=status.HTTP_201_CREATED)
async def create_scenario(scenario_data: ScenarioCreate, current_user: User = Depends(get_current_active_profile), db: AsyncSession = Depends(get_db)):
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")
    
    new_scenario = Scenario(user_id=current_user.id, name=scenario_data.name, schedule=scenario_data.schedule, is_active=scenario_data.is_active)
    db.add(new_scenario)
    await db.flush()

    await _graph_to_db(db, new_scenario, scenario_data)
    await _create_or_update_periodic_task(db, new_scenario)
    
    await db.commit()
    await db.refresh(new_scenario)
    
    nodes, edges = _db_to_graph(new_scenario)
    return ScenarioSchema(id=new_scenario.id, name=new_scenario.name, schedule=new_scenario.schedule, is_active=new_scenario.is_active, nodes=nodes, edges=edges)

@router.put("/{scenario_id}", response_model=ScenarioSchema)
async def update_scenario(scenario_id: int, scenario_data: ScenarioUpdate, current_user: User = Depends(get_current_active_profile), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == current_user.id).options(selectinload(Scenario.steps))
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")
    
    db_scenario.name = scenario_data.name
    db_scenario.schedule = scenario_data.schedule
    db_scenario.is_active = scenario_data.is_active

    await _graph_to_db(db, db_scenario, scenario_data)
    await _create_or_update_periodic_task(db, db_scenario)

    await db.commit()
    await db.refresh(db_scenario)
    nodes, edges = _db_to_graph(db_scenario)
    return ScenarioSchema(id=db_scenario.id, name=db_scenario.name, schedule=db_scenario.schedule, is_active=db_scenario.is_active, nodes=nodes, edges=edges)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(scenario_id: int, current_user: User = Depends(get_current_active_profile), db: AsyncSession = Depends(get_db)):
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
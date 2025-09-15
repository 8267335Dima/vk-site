import json
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from croniter import croniter

from app.db.session import get_db
from app.db.models import User, Scenario, ScenarioStep, ScenarioStepType
from app.api.dependencies import get_current_active_profile
from app.api.schemas.scenarios import (
    Scenario as ScenarioSchema,
    ScenarioCreate,
    ScenarioUpdate,
    AvailableCondition,
    ScenarioStepNode,
    ScenarioEdge,
)

router = APIRouter()


# =====================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================

def _db_to_graph(scenario: Scenario) -> tuple[List[ScenarioStepNode], List[ScenarioEdge]]:
    """Конвертирует ORM-модели шагов и связей в формат для React Flow."""
    nodes: List[ScenarioStepNode] = []
    edges: List[ScenarioEdge] = []

    if not scenario.steps:
        return nodes, edges

    db_id_to_frontend_id = {
        step.id: str(step.details.get("id", step.id)) for step in scenario.steps
    }

    for step in scenario.steps:
        node_id_str = db_id_to_frontend_id[step.id]

        # Тип узла для фронта
        if step.step_type == ScenarioStepType.action and step.details.get("action_type") == "start":
            node_type = "start"
        else:
            node_type = step.step_type.value

        nodes.append(
            ScenarioStepNode(
                id=node_id_str,
                type=node_type,
                data=step.details.get("data", {}),
                position={"x": step.position_x, "y": step.position_y},
            )
        )

        source_id_str = db_id_to_frontend_id[step.id]

        if step.next_step_id and step.next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.next_step_id]
            edges.append(
                ScenarioEdge(
                    id=f"e{source_id_str}-{target_id_str}",
                    source=source_id_str,
                    target=target_id_str,
                )
            )

        if step.on_success_next_step_id and step.on_success_next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.on_success_next_step_id]
            edges.append(
                ScenarioEdge(
                    id=f"e{source_id_str}-{target_id_str}-success",
                    source=source_id_str,
                    target=target_id_str,
                    sourceHandle="on_success",
                )
            )

        if step.on_failure_next_step_id and step.on_failure_next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.on_failure_next_step_id]
            edges.append(
                ScenarioEdge(
                    id=f"e{source_id_str}-{target_id_str}-failure",
                    source=source_id_str,
                    target=target_id_str,
                    sourceHandle="on_failure",
                )
            )

    return nodes, edges


def _build_steps_from_nodes(nodes: List[ScenarioStepNode]) -> Dict[str, ScenarioStep]:
    """Создаёт объекты шагов из узлов фронта (без связей)."""
    node_map: Dict[str, ScenarioStep] = {}
    for node in nodes:
        if node.type == "start":
            step_type = ScenarioStepType.action
            details = {"id": node.id, "data": node.data, "action_type": "start"}
        elif node.type == "action":
            step_type = ScenarioStepType.action
            details = {"id": node.id, "data": node.data}
        elif node.type == "condition":
            step_type = ScenarioStepType.condition
            details = {"id": node.id, "data": node.data}
        else:
            raise HTTPException(
                status_code=400, detail=f"Неизвестный тип узла: {node.type}"
            )

        step = ScenarioStep(
            step_type=step_type,
            details=details,
            position_x=node.position.get("x", 0),
            position_y=node.position.get("y", 0),
        )
        node_map[node.id] = step

    return node_map


def _apply_edges(node_map: Dict[str, ScenarioStep], edges: List[ScenarioEdge]) -> None:
    """Проставляет связи между шагами по рёбрам."""
    for edge in edges:
        source_step = node_map.get(edge.source)
        target_step = node_map.get(edge.target)
        if not source_step or not target_step:
            continue

        if source_step.step_type == ScenarioStepType.action:
            source_step.next_step_id = target_step.id
        elif source_step.step_type == ScenarioStepType.condition:
            if edge.sourceHandle == "on_success":
                source_step.on_success_next_step_id = target_step.id
            elif edge.sourceHandle == "on_failure":
                source_step.on_failure_next_step_id = target_step.id


def _find_start_step(node_map: Dict[str, ScenarioStep], nodes: List[ScenarioStepNode]) -> int | None:
    """Находит стартовый шаг (если есть)."""
    start_node = next((node for node in nodes if node.type == "start"), None)
    if start_node:
        return node_map[start_node.id].id
    return None


# =====================================================
# ЭНДПОИНТЫ
# =====================================================

@router.get("/available-conditions", response_model=List[AvailableCondition])
async def get_available_conditions():
    """Условные поля для сценариев (UI-справочник)."""
    return [
        {
            "key": "friends_count",
            "label": "Количество друзей",
            "type": "number",
            "operators": ["==", "!=", ">", "<", ">=", "<="],
        },
        {
            "key": "conversion_rate",
            "label": "Конверсия заявок (%)",
            "type": "number",
            "operators": [">", "<", ">=", "<="],
        },
        {
            "key": "day_of_week",
            "label": "День недели",
            "type": "select",
            "operators": ["==", "!="],
            "options": [
                {"value": "1", "label": "Понедельник"},
                {"value": "2", "label": "Вторник"},
                {"value": "3", "label": "Среда"},
                {"value": "4", "label": "Четверг"},
                {"value": "5", "label": "Пятница"},
                {"value": "6", "label": "Суббота"},
                {"value": "7", "label": "Воскресенье"},
            ],
        },
    ]


@router.get("", response_model=List[ScenarioSchema])
async def get_user_scenarios(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Scenario)
        .where(Scenario.user_id == current_user.id)
        .options(selectinload(Scenario.steps))
    )
    result = await db.execute(stmt)
    scenarios_db = result.scalars().unique().all()

    return [
        ScenarioSchema(
            id=s.id,
            name=s.name,
            schedule=s.schedule,
            is_active=s.is_active,
            nodes=_db_to_graph(s)[0],
            edges=_db_to_graph(s)[1],
        )
        for s in scenarios_db
    ]


@router.get("/{scenario_id}", response_model=ScenarioSchema)
async def get_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Scenario)
        .where(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
        .options(selectinload(Scenario.steps))
    )
    result = await db.execute(stmt)
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")

    nodes, edges = _db_to_graph(scenario)
    return ScenarioSchema(
        id=scenario.id,
        name=scenario.name,
        schedule=scenario.schedule,
        is_active=scenario.is_active,
        nodes=nodes,
        edges=edges,
    )


@router.post("", response_model=ScenarioSchema, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    scenario_data: ScenarioCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    new_scenario = Scenario(
        user_id=current_user.id,
        name=scenario_data.name,
        schedule=scenario_data.schedule,
        is_active=scenario_data.is_active,
    )

    node_map = _build_steps_from_nodes(scenario_data.nodes)
    new_scenario.steps = list(node_map.values())
    db.add(new_scenario)
    await db.flush()

    _apply_edges(node_map, scenario_data.edges)
    new_scenario.first_step_id = _find_start_step(node_map, scenario_data.nodes)

    await db.commit()

    await db.refresh(new_scenario)
    await db.refresh(new_scenario, attribute_names=["steps"])
    # -------------------------

    nodes, edges = _db_to_graph(new_scenario)
    return ScenarioSchema(
        id=new_scenario.id,
        name=new_scenario.name,
        schedule=new_scenario.schedule,
        is_active=new_scenario.is_active,
        nodes=nodes,
        edges=edges,
    )



@router.put("/{scenario_id}", response_model=ScenarioSchema)
async def update_scenario(
    scenario_id: int,
    scenario_data: ScenarioUpdate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Scenario)
        .where(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
        .options(selectinload(Scenario.steps))
    )
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")

    if scenario_data.schedule and not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    # обновляем базовые поля
    db_scenario.name = scenario_data.name or db_scenario.name
    db_scenario.schedule = scenario_data.schedule or db_scenario.schedule
    db_scenario.is_active = (
        scenario_data.is_active
        if scenario_data.is_active is not None
        else db_scenario.is_active
    )

    # удаляем старые шаги, если новые переданы
    if scenario_data.nodes is not None:

        db_scenario.first_step_id = None
        
        for old_step in db_scenario.steps:
            await db.delete(old_step)
        await db.flush()

        # строим новые шаги
        node_map = _build_steps_from_nodes(scenario_data.nodes)
        db_scenario.steps = list(node_map.values())
        await db.flush()

        # проставляем связи
        _apply_edges(node_map, scenario_data.edges or [])

        # находим и устанавливаем ID нового стартового шага
        new_start_step_obj = next((step for step in node_map.values() if step.details.get("action_type") == "start"), None)
        if new_start_step_obj:
            db_scenario.first_step_id = new_start_step_obj.id

    await db.commit()

    await db.refresh(db_scenario)
    await db.refresh(db_scenario, attribute_names=["steps"])

    nodes, edges = _db_to_graph(db_scenario)
    return ScenarioSchema(
        id=db_scenario.id,
        name=db_scenario.name,
        schedule=db_scenario.schedule,
        is_active=db_scenario.is_active,
        nodes=nodes,
        edges=edges,
    )


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Scenario).where(
        Scenario.id == scenario_id, Scenario.user_id == current_user.id
    )
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")

    # <<< ИЗМЕНЕНИЕ ЗДЕСЬ: РАЗРЫВАЕМ СВЯЗЬ ПЕРЕД УДАЛЕНИЕМ >>>
    # Это гарантирует, что база данных не будет блокировать удаление шагов.
    db_scenario.first_step_id = None
    await db.flush()  # Отправляем изменение в БД до основного удаления

    await db.delete(db_scenario)
    await db.commit()
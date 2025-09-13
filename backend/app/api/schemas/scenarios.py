# --- backend/app/api/schemas/scenarios.py ---
import enum
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ScenarioStepType(str, enum.Enum):
    action = "action"
    condition = "condition"

# Схемы для шагов (теперь это "узлы" графа)
class ScenarioStepNode(BaseModel):
    id: str # Фронтенд-ID узла (например, 'node_1')
    step_type: ScenarioStepType
    details: Dict[str, Any]
    position: Dict[str, float]

class ScenarioEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None # 'next', 'on_success', 'on_failure'

# --- Схемы для сценариев ---
class ScenarioBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    schedule: str = Field(..., description="CRON-строка, напр. '0 9 * * 1-5'")
    is_active: bool = False

class ScenarioCreate(ScenarioBase):
    nodes: List[ScenarioStepNode]
    edges: List[ScenarioEdge]

class ScenarioUpdate(ScenarioCreate):
    pass

class Scenario(ScenarioBase):
    id: int
    nodes: List[ScenarioStepNode]
    edges: List[ScenarioEdge]

    class Config:
        from_attributes = True

# Схема для нового эндпоинта
class ConditionOption(BaseModel):
    value: str
    label: str

class AvailableCondition(BaseModel):
    key: str
    label: str
    type: str # 'number', 'select', 'time'
    operators: List[str]
    options: Optional[List[ConditionOption]] = None
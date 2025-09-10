# backend/app/api/schemas/scenarios.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# --- Схемы для шагов ---
class ScenarioStepBase(BaseModel):
    action_type: str
    settings: Dict[str, Any]

class ScenarioStepCreate(ScenarioStepBase):
    step_order: int

class ScenarioStep(ScenarioStepBase):
    id: int
    step_order: int

    class Config:
        from_attributes = True

# --- Схемы для сценариев ---
class ScenarioBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    schedule: str = Field(..., description="CRON-строка, напр. '0 9 * * 1-5'")
    is_active: bool = False

class ScenarioCreate(ScenarioBase):
    steps: List[ScenarioStepCreate]

class ScenarioUpdate(ScenarioBase):
    steps: List[ScenarioStepCreate]

class Scenario(ScenarioBase):
    id: int
    steps: List[ScenarioStep]

    class Config:
        from_attributes = True
from pydantic import BaseModel
from typing import List, Literal, Optional
from datetime import datetime

class PlannerEvent(BaseModel):
    id: str
    type: Literal["post", "scenario", "automation"]
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: Optional[str] = None

class MasterPlanResponse(BaseModel):
    events: List[PlannerEvent]
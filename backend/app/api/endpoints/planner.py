from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, date, time, timedelta
from typing import List
from croniter import croniter

from app.db.session import get_read_db
from app.db.models import User, ScheduledPost, Scenario, Automation
from app.api.dependencies import get_current_active_profile
from app.api.schemas.planner import PlannerEvent, MasterPlanResponse

router = APIRouter()

@router.get("/master-plan", response_model=MasterPlanResponse)
async def get_master_plan(
    start_date: date,
    end_date: date,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_read_db),
):
    events: List[PlannerEvent] = []
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    posts_stmt = select(ScheduledPost).where(
        ScheduledPost.user_id == current_user.id,
        ScheduledPost.publish_at.between(start_dt, end_dt)
    )
    posts = (await db.execute(posts_stmt)).scalars().all()
    for post in posts:
        events.append(PlannerEvent(
            id=f"post_{post.id}", type="post", title=f"Пост: {post.post_text[:20]}...",
            start_time=post.publish_at, status=post.status.value
        ))

    scenarios_stmt = select(Scenario).where(Scenario.user_id == current_user.id, Scenario.is_active == True)
    scenarios = (await db.execute(scenarios_stmt)).scalars().all()
    for scenario in scenarios:
        try:
            it = croniter(scenario.schedule, start_dt)
            while (next_run := it.get_next(datetime)) <= end_dt:
                events.append(PlannerEvent(
                    id=f"scenario_{scenario.id}_{next_run.timestamp()}", type="scenario",
                    title=f"Сценарий: {scenario.name}", start_time=next_run
                ))
        except:
            continue

    automations_stmt = select(Automation).where(Automation.user_id == current_user.id, Automation.is_active == True)
    automations = (await db.execute(automations_stmt)).scalars().all()
    for automation in automations:
        if automation.automation_type == "eternal_online":
            # (Здесь нужна более сложная логика для отображения интервалов)
            pass

    events.sort(key=lambda x: x.start_time)
    return MasterPlanResponse(events=events)
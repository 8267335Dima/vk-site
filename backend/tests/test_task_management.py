# backend/tests/test_task_management.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from arq.jobs import JobStatus
from arq.connections import ArqRedis

from app.db.models import TaskHistory
from app.worker import WorkerSettings


async def test_task_history_pagination(async_client: AsyncClient, authorized_user_and_headers: tuple, db_session: AsyncSession):
    user, headers = authorized_user_and_headers
    # Очищаем старые задачи, чтобы не влиять на тест
    await db_session.execute(delete(TaskHistory).where(TaskHistory.user_id == user.id))
    # Создаем ровно 30 задач
    for i in range(30):
        db_session.add(TaskHistory(user_id=user.id, task_name=f"Task {i}", status="SUCCESS"))
    await db_session.commit()

    response = await async_client.get("/api/v1/tasks/history?page=2&size=10", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data['items']) == 10
    assert data['page'] == 2
    assert data['total'] == 30

async def test_retry_failed_task(async_client: AsyncClient, authorized_user_and_headers: tuple, db_session: AsyncSession):
    user, headers = authorized_user_and_headers
    failed_task = TaskHistory(user_id=user.id, task_name="Лайки в ленте новостей", status="FAILURE", parameters={"count": 5})
    db_session.add(failed_task)
    await db_session.commit()

    response = await async_client.post(f"/api/v1/tasks/{failed_task.id}/retry", headers=headers)
    assert response.status_code == 200
    new_task_id = response.json()['task_id']

    new_task_in_db = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == new_task_id))
    assert new_task_in_db is not None
    assert new_task_in_db.status == "PENDING"

async def test_cancel_pending_task(async_client: AsyncClient, authorized_user_and_headers: tuple, db_session: AsyncSession):
    user, headers = authorized_user_and_headers
    
    response = await async_client.post("/api/v1/tasks/run/like_feed", headers=headers, json={"count": 10})
    job_id = response.json()['task_id']
    task_in_db = await db_session.scalar(select(TaskHistory).where(TaskHistory.celery_task_id == job_id))

    cancel_response = await async_client.post(f"/api/v1/tasks/{task_in_db.id}/cancel", headers=headers)
    assert cancel_response.status_code == 202

    await db_session.refresh(task_in_db)
    assert task_in_db.status == "CANCELLED"
    
    arq_redis = ArqRedis(WorkerSettings.redis_settings)
    job_result = await arq_redis.get_job_result(job_id)
    assert job_result.status == JobStatus.aborted
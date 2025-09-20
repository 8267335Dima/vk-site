# tests/tasks/test_arq_runner.py

import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.standard_tasks import arq_task_runner
from app.db.models import TaskHistory, User, Automation
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAuthError

pytestmark = pytest.mark.anyio

async def dummy_task_logic(session, user, params, emitter):
    if params.get("should_fail"):
        raise UserActionException("Задача провалена по сценарию.")
    if params.get("should_auth_fail"):
        raise VKAuthError("Невалидный токен.", 5)
    if params.get("should_raise_unexpected"):
        raise ValueError("Что-то пошло не так!")
    return "Задача выполнена успешно."

decorated_task = arq_task_runner(dummy_task_logic)

async def test_arq_runner_success(db_session: AsyncSession, test_user: User, mock_emitter):
    task_history = TaskHistory(user_id=test_user.id, task_name="Успешный тест", status="PENDING", parameters={})
    db_session.add(task_history)
    await db_session.commit()

    await decorated_task(
        ctx={"redis_pool": AsyncMock()},
        task_history_id=task_history.id,
        session_for_test=db_session,
        emitter_for_test=mock_emitter
    )

    await db_session.refresh(task_history)
    assert task_history.status == "SUCCESS"
    assert task_history.result == "Задача выполнена успешно."

async def test_arq_runner_handles_user_action_exception(db_session: AsyncSession, test_user: User, mock_emitter):
    task_history = TaskHistory(
        user_id=test_user.id, 
        task_name="Тест сбоя", 
        status="PENDING",
        parameters={"should_fail": True}
    )
    db_session.add(task_history)
    await db_session.commit()

    await decorated_task(
        ctx={"redis_pool": AsyncMock()},
        task_history_id=task_history.id,
        session_for_test=db_session,
        emitter_for_test=mock_emitter
    )

    await db_session.refresh(task_history)
    assert task_history.status == "FAILURE"
    assert "Ошибка: Задача провалена по сценарию." in task_history.result
    mock_emitter.send_system_notification.assert_awaited_once()

async def test_arq_runner_handles_vk_auth_error_and_disables_automations(db_session: AsyncSession, test_user: User, mock_emitter):
    task_history = TaskHistory(
        user_id=test_user.id, 
        task_name="Тест авторизации", 
        status="PENDING",
        parameters={"should_auth_fail": True}
    )
    automation = Automation(user_id=test_user.id, automation_type="like_feed", is_active=True)
    db_session.add_all([task_history, automation])
    await db_session.commit()

    await decorated_task(
        ctx={"redis_pool": AsyncMock()},
        task_history_id=task_history.id,
        session_for_test=db_session,
        emitter_for_test=mock_emitter
    )

    await db_session.refresh(task_history)
    await db_session.refresh(automation)
    assert task_history.status == "FAILURE"
    assert "Ошибка авторизации VK. Токен невалиден." in task_history.result
    assert automation.is_active is False
    mock_emitter.send_system_notification.assert_awaited_with(
        db_session, 
        "Критическая ошибка: токен VK недействителен для задачи 'Тест авторизации'. Автоматизации остановлены.", 
        "error"
    )

async def test_arq_runner_handles_unexpected_exception(db_session: AsyncSession, test_user: User, mock_emitter):
    task_history = TaskHistory(
        user_id=test_user.id, 
        task_name="Тест падения", 
        status="PENDING",
        parameters={"should_raise_unexpected": True}
    )
    db_session.add(task_history)
    await db_session.commit()

    await decorated_task(
        ctx={"redis_pool": AsyncMock()},
        task_history_id=task_history.id,
        session_for_test=db_session,
        emitter_for_test=mock_emitter
    )

    await db_session.refresh(task_history)
    assert task_history.status == "FAILURE"
    assert "Внутренняя ошибка сервера: ValueError" in task_history.result
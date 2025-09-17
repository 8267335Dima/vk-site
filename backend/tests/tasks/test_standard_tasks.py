# tests/tasks/test_standard_tasks.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TaskHistory, User
from app.tasks.standard_tasks import like_feed_task
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserLimitReachedError
from app.services.vk_api import VKAuthError
from app.db.models import Automation

pytestmark = pytest.mark.asyncio

@pytest.fixture
def mock_arq_context(mocker):
    """Мокает контекст, который ARQ передает в задачу."""
    mock_redis = mocker.AsyncMock()
    return {"redis_pool": mock_redis}

@pytest.fixture
def mock_emitter(mocker, mock_arq_context):
    """Мокает эмиттер событий, чтобы не было реальных Pub/Sub сообщений."""
    emitter = RedisEventEmitter(mock_arq_context['redis_pool'])
    emitter.send_log = mocker.AsyncMock()
    emitter.send_task_status_update = mocker.AsyncMock()
    emitter.send_system_notification = mocker.AsyncMock()
    return emitter


async def test_task_runner_success(db_session: AsyncSession, test_user: User, mock_arq_context, mocker, mock_emitter):
    """Проверяет, что задача успешно выполняется и меняет статус в БД на SUCCESS."""
    mocker.patch('app.tasks.standard_tasks._run_service_method', return_value="Все прошло отлично")

    task_history = TaskHistory(user_id=test_user.id, task_name="Тест лайков", status="PENDING", parameters={"count": 10})
    db_session.add(task_history)
    # ИСПОЛЬЗУЕМ FLUSH, А НЕ COMMIT
    await db_session.flush() 
    await db_session.refresh(task_history)

    await like_feed_task(
        mock_arq_context,
        task_history.id,
        emitter_for_test=mock_emitter,
        session_for_test=db_session
    )

    # Обновлять объект не нужно, так как мы работаем в той же сессии
    assert task_history.status == "SUCCESS"
    assert task_history.result == "Все прошло отлично"
    
    mock_emitter.send_task_status_update.assert_any_call(status="STARTED", task_name="Тест лайков", created_at=task_history.created_at)
    mock_emitter.send_task_status_update.assert_called_with(status="SUCCESS", result="Все прошло отлично", task_name="Тест лайков", created_at=task_history.created_at)


async def test_task_runner_failure(db_session: AsyncSession, test_user: User, mock_arq_context, mocker, mock_emitter):
    """Проверяет, что задача падает и меняет статус в БД на FAILURE."""
    error_message = "Дневной лимит исчерпан"
    mocker.patch('app.tasks.standard_tasks._run_service_method', side_effect=UserLimitReachedError(error_message))

    task_history = TaskHistory(user_id=test_user.id, task_name="Тест с ошибкой", status="PENDING")
    db_session.add(task_history)
    # ИСПОЛЬЗУЕМ FLUSH
    await db_session.flush()
    await db_session.refresh(task_history)

    await like_feed_task(
        mock_arq_context,
        task_history.id,
        emitter_for_test=mock_emitter,
        session_for_test=db_session
    )
    
    assert task_history.status == "FAILURE"
    assert error_message in task_history.result
    
    mock_emitter.send_system_notification.assert_called_once()

async def test_task_runner_handles_vk_auth_error(db_session: AsyncSession, test_user: User, mock_arq_context, mocker, mock_emitter):
    """
    Проверяет, что при возникновении VKAuthError, задача падает с правильным сообщением,
    а все активные автоматизации пользователя деактивируются.
    """
    # Arrange:
    # 1. Создаем активную автоматизацию для пользователя.
    automation = Automation(user_id=test_user.id, automation_type="like_feed", is_active=True)
    db_session.add(automation)

    # 2. Создаем TaskHistory для запуска.
    task_history = TaskHistory(user_id=test_user.id, task_name="Тест с ошибкой авторизации", status="PENDING")
    db_session.add(task_history)
    await db_session.flush()
    await db_session.refresh(task_history)
    await db_session.refresh(automation)
    
    # Убедимся, что автоматизация активна перед тестом
    assert automation.is_active is True

    # 3. Мокаем выполнение задачи так, чтобы она выбрасывала VKAuthError.
    mocker.patch(
        'app.tasks.standard_tasks._run_service_method',
        side_effect=VKAuthError("User authorization failed: invalid access_token.", 5)
    )

    # Act: Запускаем задачу, которая должна упасть.
    await like_feed_task(
        mock_arq_context,
        task_history.id,
        emitter_for_test=mock_emitter,
        session_for_test=db_session
    )

    # Assert:
    # 1. Проверяем статус и результат в TaskHistory.
    await db_session.refresh(task_history)
    assert task_history.status == "FAILURE"
    assert "Ошибка авторизации VK. Токен невалиден." in task_history.result

    # 2. Проверяем, что автоматизация пользователя была деактивирована.
    await db_session.refresh(automation)
    assert automation.is_active is False

    # 3. Проверяем, что было отправлено системное уведомление.
    mock_emitter.send_system_notification.assert_called_once_with(
        db_session,
        "Критическая ошибка: токен VK недействителен для задачи 'Тест с ошибкой авторизации'. Автоматизации остановлены.",
        "error"
    )
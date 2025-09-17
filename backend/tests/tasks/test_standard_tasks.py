# tests/tasks/test_standard_tasks.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TaskHistory, User
from app.tasks.standard_tasks import like_feed_task, arq_task_runner
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserLimitReachedError

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
    # 1. Мокаем внутреннюю логику задачи, чтобы она просто возвращала успешный результат
    mocker.patch('app.tasks.standard_tasks._run_service_method', return_value="Все прошло отлично")

    # 2. Создаем запись о задаче в БД
    task_history = TaskHistory(user_id=test_user.id, task_name="Тест лайков", status="PENDING", parameters={"count": 10})
    db_session.add(task_history)
    await db_session.commit()
    await db_session.refresh(task_history)

    # 3. Выполняем задачу напрямую
    await like_feed_task(mock_arq_context, task_history.id, emitter_for_test=mock_emitter)

    # 4. Проверяем результат в БД
    await db_session.refresh(task_history)
    assert task_history.status == "SUCCESS"
    assert task_history.result == "Все прошло отлично"
    
    # 5. Проверяем, что эмиттер был вызван для обновления статуса
    mock_emitter.send_task_status_update.assert_any_call(status="STARTED", task_name="Тест лайков", created_at=task_history.created_at)
    mock_emitter.send_task_status_update.assert_called_with(status="SUCCESS", result="Все прошло отлично", task_name="Тест лайков", created_at=task_history.created_at)


async def test_task_runner_failure(db_session: AsyncSession, test_user: User, mock_arq_context, mocker, mock_emitter):
    """Проверяет, что задача падает и меняет статус в БД на FAILURE."""
    # 1. Мокаем внутреннюю логику, чтобы она выбрасывала исключение
    error_message = "Дневной лимит исчерпан"
    mocker.patch('app.tasks.standard_tasks._run_service_method', side_effect=UserLimitReachedError(error_message))

    # 2. Создаем запись о задаче
    task_history = TaskHistory(user_id=test_user.id, task_name="Тест с ошибкой", status="PENDING")
    db_session.add(task_history)
    await db_session.commit()

    # 3. Выполняем задачу
    await like_feed_task(mock_arq_context, task_history.id, emitter_for_test=mock_emitter)
    
    # 4. Проверяем результат
    await db_session.refresh(task_history)
    assert task_history.status == "FAILURE"
    assert error_message in task_history.result
    
    # 5. Проверяем, что было отправлено системное уведомление об ошибке
    mock_emitter.send_system_notification.assert_called_once()
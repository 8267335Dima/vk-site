# tests/services/test_scenario_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock

from app.db.models import User, Scenario, ScenarioStep, ScenarioStepType
from app.services.scenario_service import ScenarioExecutionService
from app.core.enums import TaskKey
from app.api.schemas.actions import LikeFeedRequest, EmptyRequest
from app.services.vk_api.base import VKAPIError # Импортируем Pydantic модели

pytestmark = pytest.mark.anyio


async def test_scenario_execution_linear(
    db_session: AsyncSession, test_user: User, mocker
):
    """
    Тест выполнения простого линейного сценария: Старт -> Действие 1.
    """
    # Arrange: 1. Мокаем сервисы и их зависимости
    # ИСПРАВЛЕНИЕ: Мокаем VKAPI, чтобы избежать реальных сетевых вызовов
    mock_vk_api_class = mocker.patch('app.services.scenario_service.VKAPI')
    mock_vk_instance = mock_vk_api_class.return_value
    mock_vk_instance.close = AsyncMock() # Мокаем метод close

    mock_service_class = AsyncMock()
    # Мокаем TASK_SERVICE_MAP, чтобы он возвращал наш мок-класс сервиса
    mocker.patch(
        "app.services.scenario_service.TASK_SERVICE_MAP",
        {TaskKey.LIKE_FEED.value: (lambda *args, **kwargs: mock_service_class, "like_newsfeed")}
    )
    # Мокаем TASK_CONFIG_MAP, чтобы вернуть правильную Pydantic модель
    mocker.patch(
        "app.services.scenario_service.TASK_CONFIG_MAP",
        {TaskKey.LIKE_FEED: (None, None, LikeFeedRequest)}
    )


    # Arrange: 2. Создаем структуру сценария в БД
    scenario = Scenario(user_id=test_user.id, name="Линейный тест", schedule="* * * * *", is_active=True)
    step1 = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "start"}})
    step2 = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "like_feed", "settings": {"count": 10}}})

    db_session.add_all([scenario, step1, step2])
    await db_session.flush()

    # Связываем шаги
    step1.next_step_id = step2.id
    scenario.first_step_id = step1.id
    await db_session.commit()

    # Act: 3. Запускаем сервис выполнения
    executor = ScenarioExecutionService(db=db_session, scenario_id=scenario.id, user_id=test_user.id)
    await executor.run()

    # Assert: 4. Проверяем, что мок-метод был вызван
    mock_service_class.like_newsfeed.assert_awaited_once()


async def test_scenario_execution_condition_true(
    db_session: AsyncSession, test_user: User, mocker
):
    """
    Тест выполнения сценария с условием, которое истинно (ветка 'on_success').
    """
    # Arrange: 1. Мокаем VK API
    mock_vk_api_class = mocker.patch('app.services.scenario_service.VKAPI')
    mock_instance = mock_vk_api_class.return_value
    # ИСПРАВЛЕНИЕ: Мокаем правильный метод users.get как асинхронный
    mock_instance.users.get = AsyncMock(return_value=[{"counters": {"friends": 150}}])

    # Мокаем сервисы для отслеживания вызовов
    mock_success_service = AsyncMock()
    mock_failure_service = AsyncMock()
    mocker.patch("app.services.scenario_service.TASK_SERVICE_MAP", {
        TaskKey.VIEW_STORIES.value: (lambda *args, **kwargs: mock_success_service, "view_stories"),
        TaskKey.LIKE_FEED.value: (lambda *args, **kwargs: mock_failure_service, "like_newsfeed"),
    })
    mocker.patch("app.services.scenario_service.TASK_CONFIG_MAP", {
        TaskKey.VIEW_STORIES: (None, None, EmptyRequest),
        TaskKey.LIKE_FEED: (None, None, LikeFeedRequest),
    })


    # Arrange: 2. Создаем структуру сценария
    scenario = Scenario(user_id=test_user.id, name="Условный тест", schedule="* * * * *", is_active=True)
    start_step = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "start"}})
    condition_step = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.condition, details={"data": {"metric": "friends_count", "operator": ">", "value": "100"}})
    success_step = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "view_stories"}})
    failure_step = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "like_feed"}})

    db_session.add_all([scenario, start_step, condition_step, success_step, failure_step])
    await db_session.flush()

    # Связываем шаги
    scenario.first_step_id = start_step.id
    start_step.next_step_id = condition_step.id
    condition_step.on_success_next_step_id = success_step.id
    condition_step.on_failure_next_step_id = failure_step.id
    await db_session.commit()

    # Act
    executor = ScenarioExecutionService(db=db_session, scenario_id=scenario.id, user_id=test_user.id)
    await executor.run()

    # Assert
    mock_success_service.view_stories.assert_awaited_once() # Должен быть вызван метод из ветки "успех"
    mock_failure_service.like_newsfeed.assert_not_awaited() # Метод из ветки "провал" не должен вызываться

async def test_scenario_execution_stops_on_action_failure(
    db_session: AsyncSession, test_user: User, mocker
):
    """
    Тест проверяет, что если шаг "действие" внутри сценария выбрасывает исключение,
    выполнение всей цепочки сценария останавливается.
    """
    # Arrange:
    # 1. Мокаем сервисы. Первый будет падать, второй - нет.
    mock_failing_service = AsyncMock()
    mock_failing_service.like_newsfeed.side_effect = VKAPIError("Test API error", 5)

    mock_success_service = AsyncMock()
    
    mocker.patch("app.services.scenario_service.TASK_SERVICE_MAP", {
        TaskKey.LIKE_FEED.value: (lambda *args, **kwargs: mock_failing_service, "like_newsfeed"),
        TaskKey.VIEW_STORIES.value: (lambda *args, **kwargs: mock_success_service, "view_stories"),
    })
    mocker.patch("app.services.scenario_service.TASK_CONFIG_MAP", {
        TaskKey.LIKE_FEED: (None, None, LikeFeedRequest),
        TaskKey.VIEW_STORIES: (None, None, EmptyRequest),
    })
    mocker.patch('app.services.scenario_service.VKAPI', new_callable=AsyncMock)

    # 2. Создаем сценарий: Старт -> Неудачное действие -> Успешное действие
    scenario = Scenario(user_id=test_user.id, name="Тест падения", schedule="* * * * *", is_active=True)
    step_start = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "start"}})
    step_fail = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "like_feed"}})
    step_never_run = ScenarioStep(scenario=scenario, step_type=ScenarioStepType.action, details={"data": {"action_type": "view_stories"}})
    
    db_session.add_all([scenario, step_start, step_fail, step_never_run])
    await db_session.flush()

    scenario.first_step_id = step_start.id
    step_start.next_step_id = step_fail.id
    step_fail.next_step_id = step_never_run.id
    await db_session.commit()

    # Act: Запускаем выполнение сценария
    executor = ScenarioExecutionService(db=db_session, scenario_id=scenario.id, user_id=test_user.id)
    # Оборачиваем вызов, так как сам executor может выбросить исключение, что нормально
    try:
        await executor.run()
    except VKAPIError:
        pass # Ожидаем, что исключение может "просочиться" наверх

    # Assert:
    # Проверяем, что падающий сервис был вызван
    mock_failing_service.like_newsfeed.assert_awaited_once()
    # Ключевая проверка: сервис, идущий после падающего, НЕ был вызван
    mock_success_service.view_stories.assert_not_awaited()
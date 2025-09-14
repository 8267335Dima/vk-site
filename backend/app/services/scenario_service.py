# --- backend/app/services/scenario_service.py ---
import datetime
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis

from app.db.models import Scenario, ScenarioStep, User
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
# --- ИЗМЕНЕНИЕ: Импортируем обе карты из нового, безопасного места ---
from app.tasks.service_maps import TASK_SERVICE_MAP, TASK_CONFIG_MAP
from app.services.event_emitter import RedisEventEmitter
from app.core.config import settings

log = structlog.get_logger(__name__)

class ScenarioExecutionService:
    def __init__(self, db: AsyncSession, scenario_id: int, user_id: int):
        self.db = db
        self.scenario_id = scenario_id
        self.user_id = user_id
        self.user: User | None = None
        self.scenario: Scenario | None = None
        self.steps_map: dict[int, ScenarioStep] = {}
        self.vk_api: VKAPI | None = None

    async def _initialize(self):
        stmt = select(Scenario).where(Scenario.id == self.scenario_id).options(selectinload(Scenario.steps), selectinload(Scenario.user))
        self.scenario = (await self.db.execute(stmt)).scalar_one_or_none()
        
        if not self.scenario or not self.scenario.is_active:
            log.warn("scenario.executor.inactive_or_not_found", scenario_id=self.scenario_id)
            return False
            
        self.user = self.scenario.user
        if not self.user:
            log.error("scenario.executor.user_not_found", user_id=self.user_id)
            return False

        self.steps_map = {step.id: step for step in self.scenario.steps}
        vk_token = decrypt_data(self.user.encrypted_vk_token)
        self.vk_api = VKAPI(access_token=vk_token)
        return True

    async def _evaluate_condition(self, step: ScenarioStep) -> bool:
        details = step.details['data']
        metric = details.get("metric")
        operator = details.get("operator")
        value = details.get("value")

        if not all([metric, operator, value]):
             log.warn("scenario.condition.invalid_params", step_id=step.id, details=details)
             return False
        
        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            numeric_value = value


        if metric == "friends_count":
            user_info_list = await self.vk_api.get_user_info(user_ids=str(self.user.vk_id), fields="counters")
            current_value = user_info_list[0].get("counters", {}).get("friends", 0) if user_info_list else 0
        elif metric == "day_of_week":
            current_value = datetime.datetime.utcnow().isoweekday()
        else:
            return False

        if operator == ">": return current_value > numeric_value
        if operator == "<": return current_value < numeric_value
        if operator == ">=": return current_value >= numeric_value
        if operator == "<=": return current_value <= numeric_value
        if operator == "==": return str(current_value) == str(value)
        if operator == "!=": return str(current_value) != str(value)
        
        return False

    async def run(self):
        if not await self._initialize(): return
        
        current_step_id = self.scenario.first_step_id
        step_limit = 50 
        executed_steps = 0

        while current_step_id and executed_steps < step_limit:
            executed_steps += 1
            current_step = self.steps_map.get(current_step_id)
            if not current_step:
                log.error("scenario.executor.step_not_found", step_id=current_step_id)
                break
            
            log.info("scenario.executor.processing_step", scenario_id=self.scenario_id, user_id=self.user_id, step_id=current_step.id, step_type=current_step.step_type.value)

            if current_step.step_type.value == 'action':
                action_type = current_step.details.get('data', {}).get("action_type")
                if not action_type or action_type == 'start':
                    current_step_id = current_step.next_step_id
                    continue
                
                task_info = TASK_SERVICE_MAP.get(action_type)
                if not task_info:
                    log.error("scenario.executor.unknown_action", action=action_type)
                    break
                
                ServiceClass, method_name = task_info
                
                redis_client = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)
                emitter = RedisEventEmitter(redis_client)
                emitter.set_context(self.user.id)
                
                service_instance = ServiceClass(db=self.db, user=self.user, emitter=emitter)
                
                ParamsModel = next((m for k, (_,_,m) in TASK_CONFIG_MAP.items() if k.value == action_type), None)
                if ParamsModel:
                    params = ParamsModel(**current_step.details.get('data', {}).get("settings", {}))
                    await getattr(service_instance, method_name)(params)
                else:
                    log.error("scenario.executor.params_model_not_found", action=action_type)

                await redis_client.close()
                current_step_id = current_step.next_step_id

            elif current_step.step_type.value == 'condition':
                result = await self._evaluate_condition(current_step)
                log.info("scenario.executor.condition_result", scenario_id=self.scenario_id, result=result)
                if result:
                    current_step_id = current_step.on_success_next_step_id
                else:
                    current_step_id = current_step.on_failure_next_step_id
            
            else:
                 log.error("scenario.executor.unknown_step_type", type=current_step.step_type)
                 break
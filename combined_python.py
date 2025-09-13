

# --- backend/app\admin.py ---

# backend/app/admin.py
import secrets
from datetime import timedelta
from fastapi import Request, HTTPException, status
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from jose import jwt, JWTError

from app.db.models import User, Payment, Automation, DailyStats, ActionLog
from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import AsyncSessionFactory

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        is_user_correct = secrets.compare_digest(username, settings.ADMIN_USER)
        is_password_correct = secrets.compare_digest(password, settings.ADMIN_PASSWORD)

        if is_user_correct and is_password_correct:
            access_token_expires = timedelta(hours=8)
            token_data = {"sub": username, "scope": "admin_access"}
            access_token = create_access_token(data=token_data, expires_delta=access_token_expires)
            request.session.update({"token": access_token})
            return True

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        if settings.ADMIN_IP_WHITELIST:
            allowed_ips = [ip.strip() for ip in settings.ADMIN_IP_WHITELIST.split(',')]
            if request.client and request.client.host not in allowed_ips:
                return False

        token = request.session.get("token")
        if not token:
            return False

        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            if payload.get("scope") != "admin_access":
                return False
            
            async with AsyncSessionFactory() as session:
                admin_user = await session.get(User, int(settings.ADMIN_VK_ID))
                if not admin_user or not admin_user.is_admin:
                    return False

        except JWTError:
            return False

        return True

authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.vk_id, User.plan, User.plan_expires_at, User.is_admin, User.created_at]
    form_columns = [User.plan, User.plan_expires_at, User.is_admin, User.daily_likes_limit, User.daily_add_friends_limit]
    column_searchable_list = [User.vk_id]
    column_default_sort = ("created_at", True)
    name_plural = "Пользователи"

class PaymentAdmin(ModelView, model=Payment):
    column_list = [Payment.id, Payment.user_id, Payment.plan_name, Payment.amount, Payment.status, Payment.created_at]
    column_searchable_list = [Payment.user_id]
    column_default_sort = ("created_at", True)
    name_plural = "Платежи"

class AutomationAdmin(ModelView, model=Automation):
    column_list = [Automation.user_id, Automation.automation_type, Automation.is_active, Automation.last_run_at]
    column_searchable_list = [Automation.user_id]
    name_plural = "Автоматизации"

class DailyStatsAdmin(ModelView, model=DailyStats):
    column_list = [c.name for c in DailyStats.__table__.c]
    column_default_sort = ("date", True)
    name_plural = "Дневная статистика"

class ActionLogAdmin(ModelView, model=ActionLog):
    column_list = [ActionLog.user_id, ActionLog.action_type, ActionLog.message, ActionLog.status, ActionLog.timestamp]
    column_searchable_list = [ActionLog.user_id]
    column_default_sort = ("timestamp", True)
    name_plural = "Логи действий"


def init_admin(app, engine):
    admin = Admin(app, engine, authentication_backend=authentication_backend)
    admin.add_view(UserAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(AutomationAdmin)
    admin.add_view(DailyStatsAdmin)
    admin.add_view(ActionLogAdmin)


# --- backend/app\celery_app.py ---

# backend/app/celery_app.py
from celery import Celery
from app.core.config import settings

redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url
)

celery_app.conf.broker_url = redis_url
celery_app.conf.result_backend = redis_url

celery_app.conf.task_routes = {
    'app.tasks.cron.*': {'queue': 'default'},
    'app.tasks.maintenance.*': {'queue': 'low_priority'},
    'app.tasks.profile_parser.*': {'queue': 'low_priority'},
}

celery_app.conf.update(
    task_track_started=True,
    task_default_queue='default',
    beat_dburi=settings.database_url.replace("+asyncpg", ""),
)

# --- backend/app\celery_worker.py ---

# backend/app/celery_worker.py
from celery.schedules import crontab
from app.celery_app import celery_app

from app.tasks import runner
from app.tasks import cron
from app.tasks import maintenance
from app.tasks import profile_parser


celery_app.add_periodic_task(
    crontab(hour=2, minute=5),
    cron.aggregate_daily_stats.s(),
    name='aggregate-daily-stats'
)

celery_app.add_periodic_task(
    crontab(hour=3, minute=0),
    profile_parser.snapshot_all_users_metrics.s(),
    name='snapshot-profile-metrics'
)

celery_app.add_periodic_task(
    crontab(hour=4, minute=0),
    maintenance.clear_old_task_history.s(),
    name='clear-old-task-history'
)

celery_app.add_periodic_task(
    crontab(minute='*/15'),
    cron.check_expired_plans.s(),
    name='check-expired-plans'
)

celery_app.add_periodic_task(
    crontab(minute='*/5'),
    cron.run_daily_automations.s(automation_group='standard'),
    name='run-standard-automations'
)

celery_app.add_periodic_task(
    crontab(minute='*/10'),
    cron.run_daily_automations.s(automation_group='online'),
    name='run-online-automations'
)

# --- backend/app\main.py ---

# backend/app/main.py
import asyncio
import structlog
from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from redis.asyncio import Redis 
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter

from app.celery_app import celery_app

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.admin import init_admin
from app.api.endpoints import (
    auth_router, users_router, websockets_router,
    stats_router, automations_router, billing_router,
    analytics_router, scenarios_router, notifications_router, proxies_router,
    tasks_router
)
from app.services.websocket_manager import redis_listener

configure_logging()
log = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_task = None
    try:
        redis_connection = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0", encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_connection)
        
        redis_cache_connection = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/3", encoding="utf-8")
        FastAPICache.init(RedisBackend(redis_cache_connection), prefix="fastapi-cache")
        
        redis_pubsub_connection = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)
        redis_task = asyncio.create_task(redis_listener(redis_pubsub_connection))
        
        log.info("lifespan.startup", message="Dependencies initialized.")
    except Exception as e:
        log.error("lifespan.startup.error", error=str(e), message="Could not connect to Redis.")
    
    yield
    
    if redis_task:
        redis_task.cancel()
        try: await redis_task
        except asyncio.CancelledError: log.info("lifespan.shutdown", message="Redis listener task cancelled.")

    if FastAPICache.get_backend():
        await FastAPICache.clear()
    log.info("lifespan.shutdown", message="Resources cleaned up.")

app = FastAPI(title="Zenith API", version="4.0.0", docs_url="/api/docs", redoc_url="/api/redoc", lifespan=lifespan)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

init_admin(app, engine)

if settings.ALLOWED_ORIGINS:
    # Разделяем строку по запятым и убираем лишние пробелы
    allowed_origins_list = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(',')]
else:
    # Запасной вариант для разработки, если переменная не задана
    allowed_origins_list = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list, # <-- Используем наш список
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router_v1 = APIRouter()
api_router_v1.include_router(auth_router, prefix="/auth", tags=["Аутентификация"])
api_router_v1.include_router(users_router, prefix="/users", tags=["Пользователи"])
api_router_v1.include_router(proxies_router, prefix="/proxies", tags=["Прокси"])
api_router_v1.include_router(tasks_router, prefix="/tasks", tags=["Задачи и История"])
api_router_v1.include_router(stats_router, prefix="/stats", tags=["Статистика"])
api_router_v1.include_router(automations_router, prefix="/automations", tags=["Автоматизации"])
api_router_v1.include_router(billing_router, prefix="/billing", tags=["Тарифы и оплата"])
api_router_v1.include_router(analytics_router, prefix="/analytics", tags=["Аналитика"])
api_router_v1.include_router(scenarios_router, prefix="/scenarios", tags=["Сценарии"])
api_router_v1.include_router(notifications_router, prefix="/notifications", tags=["Уведомления"])
api_router_v1.include_router(websockets_router, prefix="", tags=["WebSockets"])

app.include_router(api_router_v1, prefix="/api/v1")

@app.get("/api/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check():
    return {"status": "ok"}

# --- backend/app\__init__.py ---



# --- backend/app\api\dependencies.py ---

# backend/app/api/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db, AsyncSessionFactory
from app.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/vk")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_user_from_token(token: str, db: AsyncSession) -> User:
    """Общая логика извлечения пользователя из токена."""
    user_repo = UserRepository(db)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValidationError, ValueError):
        raise credentials_exception
    
    user = await user_repo.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
) -> User:
    """Зависимость для HTTP-запросов."""
    return await get_user_from_token(token, db)

async def get_current_user_from_ws(token: str = Query(...)) -> User:
    """
    Зависимость для аутентификации WebSocket-соединений.
    Создает собственную сессию БД, т.к. Depends(get_db) не работает в WS.
    """
    async with AsyncSessionFactory() as session:
        return await get_user_from_token(token, session)


# --- backend/app\api\__init__.py ---



# --- backend/app\api\endpoints\analytics.py ---

# backend/app/api/endpoints/analytics.py
import datetime
from collections import Counter
from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FriendsHistory, User, DailyStats, ProfileMetric
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.api.schemas.analytics import (
    AudienceAnalyticsResponse, AudienceStatItem, 
    FriendsDynamicItem, FriendsDynamicResponse,
    ActionSummaryResponse, ActionSummaryItem,
    SexDistributionResponse,
    ProfileGrowthResponse, ProfileGrowthItem 
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from pydantic import BaseModel

router = APIRouter()

class ProfileSummaryResponse(BaseModel):
    friends: int
    followers: int
    photos: int
    wall_posts: int

def calculate_age(bdate: str) -> int | None:
    try:
        parts = bdate.split('.')
        if len(parts) == 3:
            birth_date = datetime.datetime.strptime(bdate, "%d.%m.%Y")
            today = datetime.date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except (ValueError, TypeError):
        return None
    return None

def get_age_group(age: int) -> str:
    if age < 18: return "< 18"
    if 18 <= age <= 24: return "18-24"
    if 25 <= age <= 34: return "25-34"
    if 35 <= age <= 44: return "35-44"
    if age >= 45: return "45+"
    return "Не указан"

@router.get("/audience", response_model=AudienceAnalyticsResponse)
@cache(expire=21600)
async def get_audience_analytics(current_user: User = Depends(get_current_user)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)

    friends = await vk_api.get_user_friends(user_id=current_user.vk_id, fields="sex,bdate,city")
    if not friends:
        return AudienceAnalyticsResponse(city_distribution=[], age_distribution=[], sex_distribution=[])

    # --- Анализ по городам ---
    city_counter = Counter(
        friend['city']['title']
        for friend in friends
        if friend.get('city') and friend.get('city', {}).get('title') and not friend.get('deactivated')
    )
    top_cities = [
        AudienceStatItem(name=city, value=count)
        for city, count in city_counter.most_common(5)
    ]

    # --- Анализ по возрасту ---
    ages = [calculate_age(friend['bdate']) for friend in friends if friend.get('bdate') and not friend.get('deactivated')]
    age_groups = [get_age_group(age) for age in ages if age is not None]
    age_counter = Counter(age_groups)
    
    age_distribution = [
        AudienceStatItem(name=group, value=count)
        for group, count in sorted(age_counter.items())
    ]

    # --- Анализ по полу ---
    sex_counter = Counter(
        'Мужчины' if f.get('sex') == 2 else ('Женщины' if f.get('sex') == 1 else 'Не указан')
        for f in friends if not f.get('deactivated')
    )
    sex_distribution = [SexDistributionResponse(name=k, value=v) for k, v in sex_counter.items()]

    return AudienceAnalyticsResponse(
        city_distribution=top_cities,
        age_distribution=age_distribution,
        sex_distribution=sex_distribution
    )

@router.get("/profile-summary", response_model=ProfileSummaryResponse)
@cache(expire=3600) # Кеш на 1 час
async def get_profile_summary(current_user: User = Depends(get_current_user)):
    """Возвращает сводную информацию по профилю пользователя."""
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    
    # Получаем основную информацию, включая счетчики
    user_info = await vk_api.get_user_info(user_ids=str(current_user.vk_id), fields="counters")
    
    friends = user_info[0].get('counters', {}).get('friends', 0) if user_info else 0
    followers = user_info[0].get('counters', {}).get('followers', 0) if user_info else 0
    photos = user_info[0].get('counters', {}).get('photos', 0) if user_info else 0
    
    # Количество постов на стене нужно запрашивать отдельно
    wall_info = await vk_api.get_wall(owner_id=current_user.vk_id, count=1)
    wall_posts = wall_info.get('count', 0) if wall_info else 0
    
    return ProfileSummaryResponse(
        friends=friends,
        followers=followers,
        photos=photos,
        wall_posts=wall_posts
    )

@router.get("/profile-growth", response_model=ProfileGrowthResponse)
async def get_profile_growth_analytics(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)

    stmt = (
        select(ProfileMetric)
        .where(
            ProfileMetric.user_id == current_user.id,
            ProfileMetric.date.between(start_date, end_date)
        )
        .order_by(ProfileMetric.date)
    )
    result = await db.execute(stmt)
    data = result.scalars().all()
    
    response_data = [
        ProfileGrowthItem(
            date=row.date, 
            total_likes_on_content=row.total_likes_on_content,
            friends_count=row.friends_count
        ) for row in data
    ]

    return ProfileGrowthResponse(data=response_data)

@router.get("/friends-dynamic", response_model=FriendsDynamicResponse)
async def get_friends_dynamic(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)

    stmt = (
        select(FriendsHistory.date, FriendsHistory.friends_count)
        .where(
            FriendsHistory.user_id == current_user.id,
            FriendsHistory.date.between(start_date, end_date)
        )
        .order_by(FriendsHistory.date)
    )

    result = await db.execute(stmt)
    data = result.all()

    response_data = [
        FriendsDynamicItem(date=row.date, total_friends=row.friends_count)
        for row in data
    ]

    return FriendsDynamicResponse(data=response_data)

@router.get("/actions-summary", response_model=ActionSummaryResponse)
async def get_actions_summary(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)

    stmt = (
        select(
            DailyStats.date,
            (
                DailyStats.likes_count +
                DailyStats.friends_added_count +
                DailyStats.friend_requests_accepted_count +
                DailyStats.stories_viewed_count +
                DailyStats.like_friends_feed_count +
                DailyStats.friends_removed_count
            ).label("total_actions")
        )
        .where(
            DailyStats.user_id == current_user.id,
            DailyStats.date.between(start_date, end_date)
        )
        .order_by(DailyStats.date)
    )

    result = await db.execute(stmt)
    data = result.all()

    response_data = [
        ActionSummaryItem(date=row.date, total_actions=row.total_actions)
        for row in data
    ]

    return ActionSummaryResponse(data=response_data)

# --- backend/app\api\endpoints\auth.py ---

# backend/app/api/endpoints/auth.py
from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi_limiter.depends import RateLimiter

from app.db.session import get_db
from app.db.models import User, LoginHistory
from app.api.schemas.auth import TokenResponse
from app.services.vk_api import is_token_valid
from app.core.security import create_access_token, encrypt_data
from app.core.config import settings
from app.core.plans import get_limits_for_plan

router = APIRouter()

class TokenRequest(BaseModel):
    vk_token: str


async def get_request_identifier(request: Request) -> str:
    return request.client.host or "unknown"

@router.post(
    "/vk", 
    response_model=TokenResponse, 
    summary="Аутентификация или регистрация по токену VK",
    # Теперь RateLimiter будет корректно вызывать нашу async-функцию
    dependencies=[Depends(RateLimiter(times=5, minutes=1, identifier=get_request_identifier))]
)
async def login_via_vk(
    *,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token_request: TokenRequest
) -> TokenResponse:
    # ... остальная часть функции без изменений ...
    vk_token = token_request.vk_token
    
    vk_id = await is_token_valid(vk_token)
    if not vk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или просроченный токен VK.",
        )

    query = select(User).where(User.vk_id == vk_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    encrypted_token = encrypt_data(vk_token)
    
    base_plan_limits = get_limits_for_plan("Базовый")

    if user:
        user.encrypted_vk_token = encrypted_token
    else:
        user = User(
            vk_id=vk_id, 
            encrypted_vk_token=encrypted_token,
            plan="Базовый",
            plan_expires_at=datetime.utcnow() + timedelta(days=14),
            daily_likes_limit=base_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=base_plan_limits["daily_add_friends_limit"]
        )
        db.add(user)

    if str(vk_id) == settings.ADMIN_VK_ID:
        admin_limits = get_limits_for_plan("PRO")
        user.is_admin = True
        user.plan = "PRO"
        user.plan_expires_at = None
        user.daily_likes_limit = admin_limits["daily_likes_limit"]
        user.daily_add_friends_limit = admin_limits["daily_add_friends_limit"]

    await db.flush()
    await db.refresh(user)

    login_entry = LoginHistory(
        user_id=user.id,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown")
    )
    db.add(login_entry)

    user_id_for_token = user.id
    
    await db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = create_access_token(
        data={"sub": str(user_id_for_token)}, expires_delta=access_token_expires
    )

    return TokenResponse(access_token=access_token, token_type="bearer")

# --- backend/app\api\endpoints\automations.py ---

# backend/app/api/endpoints/automations.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import User, Automation
from app.api.dependencies import get_current_user
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.plans import is_feature_available_for_plan

router = APIRouter()

class AutomationStatus(BaseModel):
    automation_type: str
    is_active: bool
    settings: Dict[str, Any] | None = None
    name: str
    description: str
    is_available: bool

class AutomationUpdateRequest(BaseModel):
    is_active: bool
    settings: Dict[str, Any] | None = None

@router.get("", response_model=List[AutomationStatus])
async def get_automations_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает статусы всех автоматизаций, указывая, доступны ли они по тарифу."""
    query = select(Automation).where(Automation.user_id == current_user.id)
    result = await db.execute(query)
    user_automations_db = {auto.automation_type: auto for auto in result.scalars().all()}
    
    response_list = []
    for config_item in AUTOMATIONS_CONFIG:
        auto_type = config_item['id']
        db_item = user_automations_db.get(auto_type)
        
        # --- ИЗМЕНЕНИЕ: Используем новую, правильную функцию ---
        is_available = is_feature_available_for_plan(current_user.plan, auto_type)
        
        response_list.append(AutomationStatus(
            automation_type=auto_type,
            is_active=db_item.is_active if db_item else False,
            settings=db_item.settings if db_item else {},
            name=config_item['name'],
            description=config_item['description'],
            is_available=is_available
        ))
        
    return response_list

@router.post("/{automation_type}", response_model=AutomationStatus)
async def update_automation(
    automation_type: str,
    request_data: AutomationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Включает, выключает или настраивает автоматизацию с проверкой прав доступа."""
    # --- ИЗМЕНЕНИЕ: Используем новую, правильную функцию ---
    if request_data.is_active and not is_feature_available_for_plan(current_user.plan, automation_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Функция '{automation_type}' недоступна на вашем тарифе '{current_user.plan}'."
        )

    config_item = next((item for item in AUTOMATIONS_CONFIG if item['id'] == automation_type), None)
    if not config_item:
        raise HTTPException(status_code=404, detail="Автоматизация такого типа не найдена.")

    query = select(Automation).where(
        Automation.user_id == current_user.id,
        Automation.automation_type == automation_type
    )
    result = await db.execute(query)
    automation = result.scalar_one_or_none()

    if not automation:
        automation = Automation(
            user_id=current_user.id,
            automation_type=automation_type,
            is_active=request_data.is_active,
            settings=request_data.settings
        )
        db.add(automation)
    else:
        automation.is_active = request_data.is_active
        if request_data.settings is not None:
            # Обновляем настройки, если они пришли, а не просто заменяем
            current_settings = automation.settings or {}
            current_settings.update(request_data.settings)
            automation.settings = current_settings
    
    await db.commit()
    await db.refresh(automation)
    
    return AutomationStatus(
        automation_type=automation.automation_type,
        is_active=automation.is_active,
        settings=automation.settings,
        name=config_item['name'],
        description=config_item['description'],
        # Если мы дошли сюда, значит проверка прав прошла успешно
        is_available=is_feature_available_for_plan(current_user.plan, automation_type)
    )

# --- backend/app\api\endpoints\billing.py ---

# backend/app/api/endpoints/billing.py
import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi_cache.decorator import cache

from app.db.session import get_db
from app.db.models import User, Payment
from app.api.dependencies import get_current_user
from app.api.schemas.billing import CreatePaymentRequest, CreatePaymentResponse, AvailablePlansResponse, PlanDetail
from app.core.config_loader import PLAN_CONFIG
import structlog

from app.core.plans import get_limits_for_plan

log = structlog.get_logger(__name__)
router = APIRouter()

@router.get("/plans", response_model=AvailablePlansResponse)
@cache(expire=3600)
async def get_available_plans():
    """
    Возвращает список всех доступных для покупки тарифных планов.
    """
    available_plans = []
    for plan_id, config in PLAN_CONFIG.items():
        # Отображаем только платные и бесплатные (с ценой 0)
        if "base_price" in config:
            available_plans.append({
                "id": plan_id,
                "display_name": config.get("display_name", plan_id),
                "price": config["base_price"], 
                "currency": config.get("currency", "RUB"),
                "description": config.get("description", ""),
                "features": config.get("features", []),
                "is_popular": config.get("is_popular", False),
                "periods": config.get("periods", [])
            })
    return {"plans": available_plans}


@router.post("/create-payment", response_model=CreatePaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Создает платеж, используя цены из централизованной конфигурации.
    """
    plan_id = request.plan_id
    months = request.months
    plan_info = PLAN_CONFIG.get(plan_id)

    if not plan_info or "base_price" not in plan_info:
        raise HTTPException(status_code=400, detail="Неверное название тарифа или тариф не является платным.")

    base_price = plan_info["base_price"]
    final_price = base_price * months

    # Применяем скидку, если она есть для данного периода
    period_info = next((p for p in plan_info.get("periods", []) if p["months"] == months), None)
    if period_info and "discount_percent" in period_info:
        final_price *= (1 - period_info["discount_percent"] / 100)
    
    final_price = round(final_price, 2)

    idempotency_key = str(uuid.uuid4())
    # Здесь должна быть реальная интеграция с YooKassa
    payment_response = {
        "id": f"test_payment_{uuid.uuid4()}",
        "status": "pending",
        "amount": {"value": str(final_price), "currency": "RUB"},
        "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=2d12b192-000f-5000-9000-1121d5a37213"}
    }
    
    new_payment = Payment(
        payment_system_id=payment_response["id"],
        user_id=current_user.id,
        amount=final_price,
        status=payment_response["status"],
        plan_name=plan_id,
        months=months
    )
    db.add(new_payment)
    await db.commit()

    log.info("payment.created", user_id=current_user.id, plan=plan_id, payment_id=new_payment.id, amount=final_price)

    return CreatePaymentResponse(confirmation_url=payment_response["confirmation"]["confirmation_url"])


@router.post("/webhook", status_code=status.HTTP_200_OK, include_in_schema=False)
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Обрабатывает вебхуки от платежной системы.
    """
    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    if event.get("event") == "payment.succeeded":
        payment_data = event.get("object", {})
        payment_system_id = payment_data.get("id")
        
        if not payment_system_id:
            return {"status": "error", "message": "Payment ID missing."}

        # --- ИЗМЕНЕНИЕ: Используем транзакцию и блокировку для атомарности ---
        async with db.begin():
            # Находим платеж
            query = select(Payment).where(Payment.payment_system_id == payment_system_id)
            result = await db.execute(query)
            payment = result.scalar_one_or_none()

            # Если платеж не найден или уже обработан, выходим
            if not payment or payment.status == "succeeded":
                return {"status": "ok"}
            
            # Блокируем строку пользователя до конца транзакции
            user = await db.get(User, payment.user_id, with_for_update=True)
            if not user:
                log.error("webhook.user_not_found", user_id=payment.user_id)
                return {"status": "ok"} # Завершаем, чтобы платежная система не повторяла запрос

            # Проверяем сумму платежа
            received_amount = float(payment_data.get("amount", {}).get("value", 0))
            if abs(received_amount - payment.amount) > 0.01: # Сравнение float с погрешностью
                payment.status = "failed"
                log.error("webhook.amount_mismatch", payment_id=payment.id, expected=payment.amount, got=received_amount)
                # Коммит произойдет автоматически при выходе из блока
                return {"status": "ok"}

            # Обновляем данные пользователя
            # Если подписка еще активна - продлеваем, если нет - начинаем с текущего момента
            start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > datetime.datetime.utcnow() else datetime.datetime.utcnow()
            
            user.plan = payment.plan_name
            user.plan_expires_at = start_date + datetime.timedelta(days=30 * payment.months)
            
            # Обновляем лимиты пользователя согласно новому тарифу
            new_limits = get_limits_for_plan(user.plan)
            user.daily_likes_limit = new_limits.get("daily_likes_limit", 0)
            user.daily_add_friends_limit = new_limits.get("daily_add_friends_limit", 0)

            payment.status = "succeeded"
            
            log.info("webhook.success", user_id=user.id, plan=user.plan, expires_at=user.plan_expires_at)
            # Коммит произойдет автоматически

    return {"status": "ok"}

# --- backend/app\api\endpoints\notifications.py ---

# backend/app/api/endpoints/notifications.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.db.session import get_db
from app.db.models import User, Notification
from app.api.dependencies import get_current_user
from app.api.schemas.notifications import NotificationsResponse

router = APIRouter()

@router.get("", response_model=NotificationsResponse)
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает последние 50 уведомлений и количество непрочитанных."""
    
    # Запрос на получение уведомлений
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    notifications = result.scalars().all()

    # Запрос на подсчет непрочитанных
    count_query = (
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    count_result = await db.execute(count_query)
    unread_count = count_result.scalar_one()

    return NotificationsResponse(items=notifications, unread_count=unread_count)

@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Отмечает все уведомления пользователя как прочитанные."""
    stmt = (
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()

# --- backend/app\api\endpoints\proxies.py ---

# backend/app/api/endpoints/proxies.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import datetime

from app.db.session import get_db
from app.db.models import User, Proxy
from app.api.dependencies import get_current_user
from app.api.schemas.proxies import ProxyCreate, ProxyRead
from app.core.security import encrypt_data, decrypt_data
from app.services.proxy_service import ProxyService
# --- НОВЫЙ ИМПОРТ ---
from app.core.plans import is_feature_available_for_plan

router = APIRouter()

# --- НОВАЯ ЗАВИСИМОСТЬ ДЛЯ ПРОВЕРКИ ПРАВ ---
async def check_proxy_feature_access(current_user: User = Depends(get_current_user)):
    if not is_feature_available_for_plan(current_user.plan, "proxy_management"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Управление прокси доступно только на PRO-тарифе."
        )
    return current_user

@router.post("", response_model=ProxyRead, status_code=status.HTTP_201_CREATED)
async def add_proxy(
    proxy_data: ProxyCreate,
    current_user: User = Depends(check_proxy_feature_access), # <-- ПРОВЕРКА ПРАВ
    db: AsyncSession = Depends(get_db)
):
    """Добавляет новый прокси для пользователя и сразу проверяет его."""
    is_working, status_message = await ProxyService.check_proxy(proxy_data.proxy_url)
    
    encrypted_url = encrypt_data(proxy_data.proxy_url)

    stmt_exists = select(Proxy).where(Proxy.user_id == current_user.id, Proxy.encrypted_proxy_url == encrypted_url)
    existing = await db.execute(stmt_exists)
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Такой прокси уже существует.")

    new_proxy = Proxy(
        user_id=current_user.id,
        encrypted_proxy_url=encrypted_url,
        is_working=is_working,
        check_status_message=status_message,
        last_checked_at=datetime.datetime.utcnow()
    )
    db.add(new_proxy)
    await db.commit()
    await db.refresh(new_proxy)
    
    return ProxyRead(
        id=new_proxy.id,
        proxy_url=decrypt_data(new_proxy.encrypted_proxy_url),
        is_working=new_proxy.is_working,
        last_checked_at=new_proxy.last_checked_at,
        check_status_message=new_proxy.check_status_message
    )

@router.get("", response_model=List[ProxyRead])
async def get_user_proxies(
    current_user: User = Depends(check_proxy_feature_access) # <-- ПРОВЕРКА ПРАВ
):
    """Возвращает список всех прокси пользователя."""
    return [
        ProxyRead(
            id=p.id,
            proxy_url=decrypt_data(p.encrypted_proxy_url),
            is_working=p.is_working,
            last_checked_at=p.last_checked_at,
            check_status_message=p.check_status_message
        ) for p in current_user.proxies
    ]

@router.delete("/{proxy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy(
    proxy_id: int,
    current_user: User = Depends(check_proxy_feature_access), # <-- ПРОВЕРКА ПРАВ
    db: AsyncSession = Depends(get_db)
):
    """Удаляет прокси по ID."""
    stmt = select(Proxy).where(Proxy.id == proxy_id, Proxy.user_id == current_user.id)
    result = await db.execute(stmt)
    proxy_to_delete = result.scalar_one_or_none()
    
    if not proxy_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прокси не найден.")
    
    await db.delete(proxy_to_delete)
    await db.commit()

# --- backend/app\api\endpoints\scenarios.py ---

# backend/app/api/endpoints/scenarios.py
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from croniter import croniter
from app.db.session import get_db
from app.db.models import User, Scenario, ScenarioStep
from app.api.dependencies import get_current_user
from app.api.schemas.scenarios import Scenario as ScenarioSchema, ScenarioCreate, ScenarioUpdate
from sqlalchemy_celery_beat.models import PeriodicTask, CrontabSchedule
from app.tasks.runner import run_scenario_from_scheduler

router = APIRouter()

async def _create_or_update_periodic_task(db: AsyncSession, scenario: Scenario):
    task_name = f"scenario-{scenario.id}"

    stmt = select(PeriodicTask).where(PeriodicTask.name == task_name)
    result = await db.execute(stmt)
    periodic_task = result.scalar_one_or_none()

    if not scenario.is_active:
        if periodic_task:
            periodic_task.enabled = False
        return

    try:
        # croniter проверяет валидность, здесь мы просто разделяем строку
        minute, hour, day_of_month, month_of_year, day_of_week = scenario.schedule.split(' ')
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки. Ожидается 5 полей.")

    crontab_stmt = select(CrontabSchedule).where(
        CrontabSchedule.minute == minute, CrontabSchedule.hour == hour,
        CrontabSchedule.day_of_month == day_of_month, CrontabSchedule.day_of_week == day_of_week,
        CrontabSchedule.month_of_year == month_of_year
    )
    res = await db.execute(crontab_stmt)
    crontab = res.scalar_one_or_none()
    if not crontab:
        crontab = CrontabSchedule(
            minute=minute, hour=hour, day_of_month=day_of_month,
            day_of_week=day_of_week, month_of_year=month_of_year
        )
        db.add(crontab)
        await db.flush()

    task_args = json.dumps([scenario.id])

    if periodic_task:
        periodic_task.crontab = crontab
        periodic_task.args = task_args
        periodic_task.enabled = True
    else:
        new_task = PeriodicTask(
            name=task_name,
            task=run_scenario_from_scheduler.name,
            crontab=crontab,
            args=task_args,
            enabled=True
        )
        db.add(new_task)

@router.get("", response_model=List[ScenarioSchema])
async def get_user_scenarios(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # --- ИСПРАВЛЕНИЕ: Добавлено selectinload для предотвращения N+1 запросов ---
    stmt = select(Scenario).where(Scenario.user_id == current_user.id).options(selectinload(Scenario.steps))
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=ScenarioSchema, status_code=status.HTTP_201_CREATED)
async def create_scenario(scenario_data: ScenarioCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    new_scenario = Scenario(user_id=current_user.id, name=scenario_data.name, schedule=scenario_data.schedule, is_active=scenario_data.is_active)
    db.add(new_scenario)
    await db.flush()

    new_steps = [ScenarioStep(scenario_id=new_scenario.id, **step.model_dump()) for step in scenario_data.steps]
    db.add_all(new_steps)
    
    await _create_or_update_periodic_task(db, new_scenario)
    await db.commit()
    await db.refresh(new_scenario)
    return new_scenario

@router.put("/{scenario_id}", response_model=ScenarioSchema)
async def update_scenario(scenario_id: int, scenario_data: ScenarioUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == current_user.id).options(selectinload(Scenario.steps))
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    db_scenario.name = scenario_data.name
    db_scenario.schedule = scenario_data.schedule
    db_scenario.is_active = scenario_data.is_active
    
    # Полное удаление и создание шагов - самый простой и надежный способ
    for step in db_scenario.steps:
        await db.delete(step)
    await db.flush()

    new_steps = [ScenarioStep(scenario_id=db_scenario.id, **step.model_dump()) for step in scenario_data.steps]
    db.add_all(new_steps)
    
    await _create_or_update_periodic_task(db, db_scenario)
    await db.commit()
    await db.refresh(db_scenario)
    return db_scenario

@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(scenario_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    
    task_name = f"scenario-{db_scenario.id}"
    stmt_task = select(PeriodicTask).where(PeriodicTask.name == task_name)
    res_task = await db.execute(stmt_task)
    periodic_task = res_task.scalar_one_or_none()
    if periodic_task:
        await db.delete(periodic_task)
    
    await db.delete(db_scenario)
    await db.commit()

# --- backend/app\api\endpoints\stats.py ---

# backend/app/api/endpoints/stats.py
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi_cache.decorator import cache

from app.db.session import get_db
from app.db.models import User, DailyStats
from app.api.dependencies import get_current_user
from app.api.schemas.stats import (
    FriendsAnalyticsResponse, ActivityStatsResponse, DailyActivity,
    FriendsDynamicResponse, FriendsDynamicItem
)
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data

router = APIRouter()

@router.get("/friends-analytics", response_model=FriendsAnalyticsResponse)
@cache(expire=3600) # Кешируем на 1 час
async def get_friends_analytics(current_user: User = Depends(get_current_user)):
    """Возвращает гендерное распределение друзей. Результат кэшируется."""
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    # Прокси для этого запроса не так важен, но можно добавить при необходимости
    vk_api = VKAPI(access_token=vk_token, proxy=None)
    
    try:
        friends = await vk_api.get_user_friends(user_id=current_user.vk_id, fields="sex")
    except VKAPIError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=f"Ошибка VK API: {e.message}")

    analytics = {"male_count": 0, "female_count": 0, "other_count": 0}
    if friends:
        for friend in friends:
            sex = friend.get("sex")
            if sex == 1:
                analytics["female_count"] += 1
            elif sex == 2:
                analytics["male_count"] += 1
            else:
                analytics["other_count"] += 1
    return FriendsAnalyticsResponse(**analytics)

@router.get("/activity", response_model=ActivityStatsResponse)
async def get_activity_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Возвращает статистику по действиям за последние N дней."""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days - 1)
    
    query = (
        select(DailyStats)
        .where(DailyStats.user_id == current_user.id)
        .where(DailyStats.date >= start_date)
        .order_by(DailyStats.date)
    )
    result = await db.execute(query)
    stats = result.scalars().all()
    
    stats_map = {s.date: s for s in stats}
    
    response_data = []
    for i in range(days):
        current_date = start_date + datetime.timedelta(days=i)
        stat_entry = stats_map.get(current_date)
        if stat_entry:
            response_data.append(DailyActivity(
                date=current_date,
                likes=stat_entry.likes_count,
                friends_added=stat_entry.friends_added_count,
                requests_accepted=stat_entry.friend_requests_accepted_count
            ))
        else:
            response_data.append(DailyActivity(
                date=current_date,
                likes=0,
                friends_added=0,
                requests_accepted=0
            ))
            
    return ActivityStatsResponse(period_days=days, data=response_data)

# --- backend/app\api\endpoints\tasks.py ---

# backend/app/api/endpoints/tasks.py
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.celery_app import celery_app # <-- НОВЫЙ ИМПОРТ
from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest
)
from app.api.schemas.tasks import ActionResponse, PaginatedTasksResponse
from app.tasks.runner import (
    accept_friend_requests, like_feed, add_recommended_friends,
    view_stories, remove_friends_by_criteria, mass_messaging
)
from app.core.plans import get_plan_config, is_feature_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG

router = APIRouter()

TASK_ENDPOINT_MAP = {
    'accept_friends': (accept_friend_requests, AcceptFriendsRequest, 'filters'),
    'like_feed': (like_feed, LikeFeedRequest, None),
    'add_recommended': (add_recommended_friends, AddFriendsRequest, None),
    'view_stories': (view_stories, EmptyRequest, None),
    'remove_friends': (remove_friends_by_criteria, RemoveFriendsRequest, None),
    'mass_messaging': (mass_messaging, MassMessagingRequest, None),
}

async def _enqueue_task(
    user: User, db: AsyncSession, task_key: str, request_data: BaseModel, original_task_name: Optional[str] = None
):
    """Универсальная функция для постановки задачи в очередь."""
    plan_config = get_plan_config(user.plan)
    
    max_concurrent = plan_config.get("limits", {}).get("max_concurrent_tasks")
    if max_concurrent is not None:
        active_tasks_query = select(func.count(TaskHistory.id)).where(
            TaskHistory.user_id == user.id,
            TaskHistory.status.in_(["PENDING", "STARTED"])
        )
        active_tasks_count = await db.scalar(active_tasks_query)
        if active_tasks_count >= max_concurrent:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Достигнут лимит на одновременное выполнение задач ({max_concurrent}). Дождитесь завершения текущих."
            )

    if not is_feature_available_for_plan(user.plan, task_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Действие недоступно на вашем тарифе '{user.plan}'.")

    
    task_func, _, params_key = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not task_func:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    
    task_display_name = original_task_name
    if not task_display_name:
        task_config = next((item for item in AUTOMATIONS_CONFIG if item['id'] == task_key), {})
        task_display_name = task_config.get('name', "Неизвестная задача")

    task_history = TaskHistory(
        user_id=user.id, task_name=task_display_name, status="PENDING",
        parameters=request_data.model_dump(exclude_unset=True)
    )
    db.add(task_history)
    await db.flush()

    celery_kwargs = request_data.model_dump()

    task_result = task_func.apply_async(
        kwargs={'task_history_id': task_history.id, **celery_kwargs},
        queue='high_priority'
    )
    task_history.celery_task_id = task_result.id
    await db.commit()
    
    return ActionResponse(
        message=f"Задача '{task_display_name}' успешно добавлена в очередь.",
        task_id=task_result.id
    )


@router.post("/run/{task_key}", response_model=ActionResponse)
async def run_any_task(
    task_key: str,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Единый эндпоинт для запуска любой задачи."""
    _, RequestModel, _ = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not RequestModel:
        raise HTTPException(status_code=404, detail="Задача не найдена.")
    
    try:
        validated_data = RequestModel(**request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return await _enqueue_task(current_user, db, task_key, validated_data)


@router.get("/history", response_model=PaginatedTasksResponse)
async def get_user_task_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None, description="Фильтр по статусу. Если пустой - вернутся все.")
):
    offset = (page - 1) * size
    base_query = select(TaskHistory).where(TaskHistory.user_id == current_user.id)
    
    if status and status.strip():
        base_query = base_query.where(TaskHistory.status == status.upper())
        
    tasks_query = base_query.order_by(TaskHistory.created_at.desc()).offset(offset).limit(size)
    count_query = select(func.count()).select_from(base_query.subquery())
    
    tasks_result = await db.execute(tasks_query)
    total_result = await db.execute(count_query)
    
    tasks = tasks_result.scalars().all()
    total = total_result.scalar_one()
    
    return PaginatedTasksResponse(
        items=tasks, total=total, page=page, size=size,
        has_more=(offset + len(tasks)) < total
    )

@router.post("/{task_history_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(
    task_history_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Отменяет задачу, находящуюся в очереди или в процессе выполнения."""
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status not in ["PENDING", "STARTED", "RETRY"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отменить можно только задачи в очереди или в процессе выполнения.")

    if task.celery_task_id:
        celery_app.control.revoke(task.celery_task_id, terminate=True)
    
    task.status = "CANCELLED"
    task.result = "Задача отменена пользователем."
    await db.commit()
    return {"message": "Запрос на отмену задачи отправлен."}

@router.post("/{task_history_id}/retry", response_model=ActionResponse)
async def retry_task(
    task_history_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Повторно запускает задачу, которая завершилась с ошибкой."""
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status != "FAILURE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Повторить можно только задачу, завершившуюся с ошибкой.")

    # Пытаемся определить task_key по названию
    task_key = next((item['id'] for item in AUTOMATIONS_CONFIG if item['name'] == task.task_name), None)
    if not task_key:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось определить тип задачи для повторного запуска.")
    
    _, RequestModel, _ = TASK_ENDPOINT_MAP.get(task_key, (None, None, None))
    if not RequestModel:
        raise HTTPException(status_code=404, detail="Модель задачи не найдена.")

    validated_data = RequestModel(**(task.parameters or {}))
    
    return await _enqueue_task(current_user, db, task_key, validated_data, original_task_name=task.task_name)

# --- backend/app\api\endpoints\users.py ---

# backend/app/api/endpoints/users.py - ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСЯ

from fastapi import APIRouter, Depends, HTTPException, status, Query # <-- Добавлен Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import User, DelayProfile
from app.api.dependencies import get_current_user
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository
from app.core.plans import get_features_for_plan, is_feature_available_for_plan
# --- НОВЫЙ ИМПОРТ ---
from app.api.schemas.users import TaskInfoResponse


router = APIRouter()

class UserMeResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    photo_200: str
    status: str = ""
    counters: Optional[Dict[str, Any]] = None
    plan: str
    plan_expires_at: Optional[datetime] = None
    is_admin: bool
    delay_profile: str
    is_plan_active: bool
    available_features: List[str]

class DailyLimitsResponse(BaseModel):
    likes_limit: int
    likes_today: int
    friends_add_limit: int
    friends_add_today: int

class UpdateDelayProfileRequest(BaseModel):
    delay_profile: DelayProfile

@router.get("/me", response_model=UserMeResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Получает полную информацию о текущем пользователе из VK и нашей БД."""
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    if not vk_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Токен доступа недействителен. Пожалуйста, авторизуйтесь заново."
        )
        
    vk_api = VKAPI(access_token=vk_token)
    
    try:
        user_info_vk = await vk_api.get_user_info()
    except VKAPIError as e:
         raise HTTPException(
             status_code=status.HTTP_424_FAILED_DEPENDENCY, 
             detail=f"Ошибка VK API: {e.message}"
        )

    if not user_info_vk:
        raise HTTPException(status_code=404, detail="Не удалось получить информацию из VK.")

    is_plan_active = True
    plan_name = current_user.plan
    if current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        is_plan_active = False
        plan_name = "Expired"

    features = get_features_for_plan(plan_name)
    
    return {
        **user_info_vk,
        "plan": current_user.plan,
        "plan_expires_at": current_user.plan_expires_at,
        "is_admin": current_user.is_admin,
        "delay_profile": current_user.delay_profile.value,
        "is_plan_active": is_plan_active,
        "available_features": features,
    }

@router.get("/me/limits", response_model=DailyLimitsResponse)
async def get_daily_limits(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает текущие дневные лимиты и использование."""
    stats_repo = StatsRepository(db)
    today_stats = await stats_repo.get_or_create_today_stats(current_user.id)

    return DailyLimitsResponse(
        likes_limit=current_user.daily_likes_limit,
        likes_today=today_stats.likes_count,
        friends_add_limit=current_user.daily_add_friends_limit,
        friends_add_today=today_stats.friends_added_count
    )

@router.put("/me/delay-profile", response_model=UserMeResponse)
async def update_user_delay_profile(
    request_data: UpdateDelayProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Обновляет профиль задержек (скорость работы) пользователя."""
    feature_key = 'fast_slow_delay_profile'
    if request_data.delay_profile != DelayProfile.normal and not is_feature_available_for_plan(current_user.plan, feature_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Смена скорости доступна только на PRO тарифе.")
        
    current_user.delay_profile = request_data.delay_profile
    await db.commit()
    return await read_users_me(current_user)

# --- НОВЫЙ ЭНДПОИНТ ---
@router.get("/task-info", response_model=TaskInfoResponse)
async def get_task_info(
    task_key: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    """
    Возвращает дополнительную информацию для модального окна задачи.
    - Для 'accept_friends': количество входящих заявок.
    - Для 'remove_friends': общее количество друзей.
    """
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    count = 0

    try:
        if task_key == "accept_friends":
            response = await vk_api.get_incoming_friend_requests()
            if response and "items" in response:
                count = len(response["items"])
        
        elif task_key == "remove_friends":
            # Используем get_user_info, так как это эффективнее
            user_info = await vk_api.get_user_info(user_ids=str(current_user.vk_id))
            if user_info and "counters" in user_info:
                count = user_info["counters"].get("friends", 0)

    except VKAPIError as e:
        # Не блокируем фронтенд, если VK API недоступен, просто вернем 0
        # В реальном приложении можно добавить логирование
        print(f"Could not fetch task info for {task_key} due to VK API error: {e}")
        count = 0

    return TaskInfoResponse(count=count)

# --- backend/app\api\endpoints\websockets.py ---

# backend/app/api/endpoints/websockets.py
from fastapi import APIRouter, WebSocket, status, Depends, Query
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_from_ws # <--- Используем готовую зависимость
from app.db.session import get_db
from app.services.websocket_manager import manager
import structlog

from app.db.models import User

log = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user: User = Depends(get_current_user_from_ws)
):
    """
    Эндпоинт для WebSocket-соединения.
    Аутентификация по токену в query-параметре `token`.
    """
    if not user:
        # Эта проверка может быть излишней, т.к. зависимость уже выбросит исключение,
        # но для ясности оставим.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user.id)
    log.info("websocket.connected", user_id=user.id)
    try:
        while True:
            # Просто поддерживаем соединение открытым
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        log.info("websocket.disconnected", user_id=user.id)

# --- backend/app\api\endpoints\__init__.py ---

# backend/app/api/endpoints/__init__.py

# Этот файл собирает все роутеры из других файлов в этой директории,
# чтобы их можно было удобно импортировать и зарегистрировать в main.py

from .auth import router as auth_router
from .users import router as users_router
from .proxies import router as proxies_router
from .tasks import router as tasks_router
from .stats import router as stats_router
from .automations import router as automations_router
from .billing import router as billing_router
from .analytics import router as analytics_router
from .scenarios import router as scenarios_router
from .notifications import router as notifications_router
from .websockets import router as websockets_router
from .users import router as users_router


# --- backend/app\api\schemas\actions.py ---

# backend/app/api/schemas/actions.py

from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class ActionFilters(BaseModel):
    """Общая модель для всех фильтров задач."""
    sex: Optional[Literal[0, 1, 2]] = 0 
    is_online: Optional[bool] = False
    last_seen_hours: Optional[int] = Field(None, ge=1)
    allow_closed_profiles: bool = False
    status_keyword: Optional[str] = Field(None, max_length=100) # <-- НОВЫЙ ФИЛЬТР

    # Фильтры для чистки друзей
    remove_banned: Optional[bool] = True
    last_seen_days: Optional[int] = Field(None, ge=1)

    # Гибкие поля для количества друзей/подписчиков
    min_friends: Optional[int] = Field(None, ge=0)
    max_friends: Optional[int] = Field(None, ge=0)
    min_followers: Optional[int] = Field(None, ge=0)
    max_followers: Optional[int] = Field(None, ge=0)

class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']

class BaseCountRequest(BaseModel):
    count: int = Field(50, ge=1)

class AddFriendsRequest(BaseCountRequest):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    like_config: LikeAfterAddConfig = Field(default_factory=LikeAfterAddConfig)
    send_message_on_add: bool = False
    message_text: Optional[str] = Field(None, max_length=500)

class LikeFeedRequest(BaseCountRequest):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class RemoveFriendsRequest(BaseCountRequest):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class AcceptFriendsRequest(BaseModel):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class MassMessagingRequest(BaseCountRequest):
    filters: ActionFilters = Field(default_factory=ActionFilters)
    message_text: str = Field(..., min_length=1, max_length=1000)
    only_new_dialogs: bool = Field(False, description="Отправлять только тем, с кем еще не было переписки.")

class EmptyRequest(BaseModel):
    pass

# --- backend/app\api\schemas\analytics.py ---

# backend/app/api/schemas/analytics.py
from pydantic import BaseModel, Field
from typing import List
from datetime import date

class AudienceStatItem(BaseModel):
    name: str = Field(..., description="Название (город, возрастная группа)")
    value: int = Field(..., description="Количество пользователей")

class SexDistributionResponse(BaseModel):
    name: str
    value: int

class AudienceAnalyticsResponse(BaseModel):
    city_distribution: List[AudienceStatItem]
    age_distribution: List[AudienceStatItem]
    sex_distribution: List[SexDistributionResponse]

class FriendsDynamicItem(BaseModel):
    date: date
    total_friends: int

class FriendsDynamicResponse(BaseModel):
    data: List[FriendsDynamicItem]

class ActionSummaryItem(BaseModel):
    date: date
    total_actions: int

class ActionSummaryResponse(BaseModel):
    data: List[ActionSummaryItem]

class ProfileGrowthItem(BaseModel):
    date: date
    total_likes_on_content: int
    friends_count: int

class ProfileGrowthResponse(BaseModel):
    data: List[ProfileGrowthItem]

# --- backend/app\api\schemas\auth.py ---

# backend/app/api/schemas/auth.py
from pydantic import BaseModel

class TokenRequest(BaseModel):
    vk_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# --- backend/app\api\schemas\billing.py ---

# backend/app/api/schemas/billing.py
from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class PlanDetail(BaseModel):
    """Детальная информация о тарифном плане для отображения на фронтенде."""
    id: str = Field(..., description="Идентификатор плана (напр., 'Plus', 'PRO')")
    display_name: str = Field(..., description="Человекочитаемое название тарифа")
    price: float = Field(..., description="Цена тарифа")
    currency: str = Field(..., description="Валюта")
    description: str = Field(..., description="Описание тарифа")
    # --- ИСПРАВЛЕНИЕ: Добавлены новые поля ---
    features: List[str] = Field([], description="Список возможностей тарифа")
    is_popular: Optional[bool] = Field(False, description="Является ли тариф популярным выбором")


class AvailablePlansResponse(BaseModel):
    """Ответ со списком доступных для покупки планов."""
    plans: List[PlanDetail]

class CreatePaymentRequest(BaseModel):
    plan_name: str = Field(..., description="Идентификатор тарифа для покупки (напр., 'Plus')")

class CreatePaymentResponse(BaseModel):
    confirmation_url: str

# --- backend/app\api\schemas\notifications.py ---

# backend/app/api/schemas/notifications.py
from pydantic import BaseModel
from datetime import datetime
from typing import List

class Notification(BaseModel):
    id: int
    message: str
    level: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationsResponse(BaseModel):
    items: List[Notification]
    unread_count: int

# --- backend/app\api\schemas\proxies.py ---

# backend/app/api/schemas/proxies.py
from pydantic import BaseModel, Field
from datetime import datetime

class ProxyBase(BaseModel):
    proxy_url: str = Field(..., description="Строка прокси, например http://user:pass@host:port")

class ProxyCreate(ProxyBase):
    pass

class ProxyRead(ProxyBase):
    id: int
    is_working: bool
    last_checked_at: datetime
    check_status_message: str | None = None

    class Config:
        from_attributes = True

class ProxyTestResponse(BaseModel):
    is_working: bool
    status_message: str

# --- backend/app\api\schemas\scenarios.py ---

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

# --- backend/app\api\schemas\stats.py ---

# backend/app/api/schemas/stats.py
from pydantic import BaseModel
from typing import List
from datetime import date

class FriendsAnalyticsResponse(BaseModel):
    male_count: int
    female_count: int
    other_count: int

class DailyActivity(BaseModel):
    date: date
    likes: int
    friends_added: int
    requests_accepted: int

class ActivityStatsResponse(BaseModel):
    period_days: int
    data: List[DailyActivity]

# --- НОВЫЕ СХЕМЫ ---
class FriendsDynamicItem(BaseModel):
    date: date
    total_friends: int

class FriendsDynamicResponse(BaseModel):
    data: List[FriendsDynamicItem]

# --- backend/app\api\schemas\tasks.py ---

# backend/app/api/schemas/tasks.py
import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any

# --- Схема для ответа после запуска любой задачи ---
class ActionResponse(BaseModel):
    status: str = "success"
    message: str
    task_id: str

# --- Схемы для отображения истории задач ---
class TaskHistoryRead(BaseModel):
    id: int
    celery_task_id: Optional[str] = None
    task_name: str
    status: str
    parameters: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    model_config = ConfigDict(from_attributes=True)


class PaginatedTasksResponse(BaseModel):
    items: List[TaskHistoryRead]
    total: int
    page: int
    size: int
    has_more: bool

# --- backend/app\api\schemas\users.py ---

# backend/app/api/schemas/users.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Literal
from datetime import datetime

class UserBase(BaseModel):
    id: int
    vk_id: int
    model_config = ConfigDict(from_attributes=True)

class ProxyUpdateRequest(BaseModel):
    proxy: Optional[str] = Field(None, description="Строка прокси, например http://user:pass@host:port")

class UserMeResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    photo_200: str
    status: str = ""
    counters: Optional[Dict[str, Any]] = None
    plan: str
    plan_expires_at: Optional[datetime] = None
    is_admin: bool
    delay_profile: str
    proxy: Optional[str] = None

class TaskInfoResponse(BaseModel):
    count: int

# --- backend/app\api\schemas\__init__.py ---



# --- backend/app\core\config.py ---

# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

# Определяем путь к .env файлу относительно этого файла.
# Это делает путь независимым от того, откуда запускается приложение.
# (VK_SITE/backend/app/core/ -> VK_SITE/.env)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    REDIS_HOST: str
    REDIS_PORT: int

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    SECRET_KEY: str
    ENCRYPTION_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    VK_API_VERSION: str
    ADMIN_VK_ID: str
    
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str

    ADMIN_USER: str
    ADMIN_PASSWORD: str
    ADMIN_IP_WHITELIST: Optional[str] = None

    ALLOWED_ORIGINS: str

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding='utf-8',
        extra='ignore'
    )

settings = Settings()

# --- backend/app\core\config_loader.py ---

# backend/app/core/config_loader.py
import yaml
from pathlib import Path
from functools import lru_cache

# Определяем путь к директории с конфигами относительно текущего файла
CONFIG_PATH = Path(__file__).parent / "configs"

@lru_cache(maxsize=None)
def load_plans_config() -> dict:
    """Загружает и кеширует конфигурацию тарифных планов."""
    config_file = CONFIG_PATH / "plans.yml"
    if not config_file.is_file():
        raise FileNotFoundError("Configuration file for plans not found: plans.yml")
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

@lru_cache(maxsize=None)
def load_automations_config() -> list:
    """Загружает и кеширует конфигурацию типов автоматизаций."""
    config_file = CONFIG_PATH / "automations.yml"
    if not config_file.is_file():
        raise FileNotFoundError("Configuration file for automations not found: automations.yml")
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

# Загружаем конфиги при старте модуля, чтобы проверить их наличие
try:
    PLAN_CONFIG = load_plans_config()
    AUTOMATIONS_CONFIG = load_automations_config()
except FileNotFoundError as e:
    print(f"CRITICAL ERROR: {e}")
    # В реальном приложении здесь можно остановить запуск
    exit(1)

# --- backend/app\core\exceptions.py ---

# backend/app/core/exceptions.py

class BaseAppException(Exception):
    """Базовое исключение для приложения."""
    pass

class UserActionException(BaseAppException):
    """Базовое исключение для ошибок во время выполнения пользовательских задач."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class UserLimitReachedError(UserActionException):
    """Вызывается, когда пользователь достигает дневного лимита."""
    pass

class InvalidActionSettingsError(UserActionException):
    """Вызывается, если настройки для действия некорректны."""
    pass

class AccountDeactivatedError(UserActionException):
    """Вызывается, если аккаунт пользователя ВКонтакте деактивирован."""
    pass

# --- backend/app\core\logging.py ---

# backend/app/core/logging.py
import logging
import sys
import structlog

def configure_logging():
    """Настраивает structlog для вывода структурированных JSON логов."""
    
    # Конфигурация для стандартного модуля logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    # Цепочка обработчиков для structlog
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [
            # Этот обработчик подготавливает данные для рендеринга
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Настраиваем рендерер, который будет выводить логи в формате JSON
    # Это ключевой шаг для интеграции с Loki/Grafana
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        # Эти обработчики будут применены только к записям, созданным через structlog
        foreign_pre_chain=shared_processors,
    )

    # Применяем наш JSON-форматтер к корневому логгеру
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Пример использования:
    # log = structlog.get_logger(__name__)
    # log.info("logging_configured", detail="Structured logging is ready.")

# --- backend/app\core\plans.py ---

# backend/app/core/plans.py
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG

def get_plan_config(plan_name: str) -> dict:
    """Безопасно получает конфигурацию плана, возвращая 'Expired' если план не найден."""
    return PLAN_CONFIG.get(plan_name, PLAN_CONFIG.get("Expired", {}))

def get_limits_for_plan(plan_name: str) -> dict:
    """Возвращает словарь с лимитами для указанного плана."""
    plan_data = get_plan_config(plan_name)
    return plan_data.get("limits", {}).copy()

def get_all_feature_keys() -> list[str]:
    """Возвращает список всех возможных ключей фич из конфига."""
    automation_ids = [item.get('id') for item in AUTOMATIONS_CONFIG if item.get('id')]
    # Добавляем другие "виртуальные" фичи, которые не являются задачами
    other_features = [
        'proxy_management', 
        'scenarios', 
        'profile_growth_analytics', 
        'fast_slow_delay_profile',
        'automations_center' # Доступ к панели автоматизаций
    ]
    return list(set(automation_ids + other_features))

def is_feature_available_for_plan(plan_name: str, feature_id: str) -> bool:
    """Проверяет, доступна ли указанная фича для данного тарифного плана."""
    plan_data = get_plan_config(plan_name)
    available_features = plan_data.get("available_features", [])
    
    # Если в тарифе указана '*', значит доступны все функции
    if available_features == "*":
        return True
    
    return feature_id in available_features

def get_features_for_plan(plan_name: str) -> list[str]:
    """
    Возвращает полный список доступных ключей фич для тарифного плана.
    Обрабатывает wildcard '*' для PRO тарифов.
    """
    plan_data = get_plan_config(plan_name)
    available = plan_data.get("available_features", [])
    
    if available == "*":
        return get_all_feature_keys() # Если '*', возвращаем все возможные фичи
    
    return available if isinstance(available, list) else []

# --- backend/app\core\security.py ---

# backend/app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from cryptography.fernet import Fernet
from app.core.config import settings

try:
    cipher_suite = Fernet(settings.ENCRYPTION_KEY.encode())
except Exception:
    raise ValueError("Invalid ENCRYPTION_KEY in .env file. Please generate a valid Fernet key.")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def encrypt_data(data: Optional[str]) -> Optional[str]:
    """Шифрует строку с использованием Fernet, обрабатывает None."""
    if data is None:
        return None
    return cipher_suite.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: Optional[str]) -> Optional[str]:
    """Дешифрует строку с использованием Fernet, обрабатывает None."""
    if encrypted_data is None:
        return None
    try:
        return cipher_suite.decrypt(encrypted_data.encode()).decode()
    except Exception:
        # В случае невалидных данных возвращаем None
        return None

# --- backend/app\core\tracing.py ---

# backend/app/core/tracing.py
import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

log = structlog.get_logger(__name__)

def setup_tracing(app: FastAPI):
    """
    Настраивает OpenTelemetry для трассировки запросов.
    В данный момент выводит трейсы в консоль для отладки.
    """
    try:
        # Устанавливаем ресурс (имя сервиса)
        resource = Resource(attributes={"service.name": "social-pulse-backend"})

        # Настраиваем провайдер трассировки
        provider = TracerProvider(resource=resource)

        # Для локальной отладки будем выводить трейсы в консоль
        # В production это заменяется на OTLP Exporter, который отправляет данные
        # в Jaeger, Grafana Tempo, Datadog и т.д.
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)

        # Устанавливаем глобальный провайдер
        trace.set_tracer_provider(provider)

        # Инструментируем FastAPI приложение
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        
        log.info("tracing.setup.success", message="OpenTelemetry tracing configured successfully.")

    except Exception as e:
        log.error("tracing.setup.failed", error=str(e))

# --- backend/app\core\__init__.py ---



# --- backend/app\db\base.py ---

# backend/app/db/base.py

from sqlalchemy.orm import declarative_base

# Базовый класс для всех моделей SQLAlchemy
Base = declarative_base()

# --- backend/app\db\models.py ---

# backend/app/db/models.py
import datetime
import enum
from sqlalchemy import (
    Column, Float, Integer, String, DateTime, ForeignKey, BigInteger, Date,
    UniqueConstraint, text, Enum, Boolean, Index, JSON, Text
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class DelayProfile(enum.Enum):
    slow = "slow"
    normal = "normal"
    fast = "fast"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    vk_id = Column(BigInteger, unique=True, index=True, nullable=False)
    encrypted_vk_token = Column(String, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    plan = Column(String, nullable=False, server_default='Базовый')
    plan_expires_at = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, nullable=False, server_default='false')

    daily_likes_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_add_friends_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_message_limit = Column(Integer, nullable=False, server_default=text('0')) # <-- НОВОЕ ПОЛЕ
    
    delay_profile = Column(Enum(DelayProfile), nullable=False, server_default=DelayProfile.normal.name)

    # Relationships
    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    task_history = relationship("TaskHistory", back_populates="user", cascade="all, delete-orphan")
    daily_stats = relationship("DailyStats", back_populates="user", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")
    profile_metrics = relationship("ProfileMetric", back_populates="user", cascade="all, delete-orphan")

class LoginHistory(Base):
    __tablename__ = "login_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    user = relationship("User")


class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_proxy_url = Column(String, nullable=False)
    is_working = Column(Boolean, default=True, nullable=False, index=True)
    last_checked_at = Column(DateTime, default=datetime.datetime.utcnow)
    check_status_message = Column(String, nullable=True)
    
    user = relationship("User", back_populates="proxies")
    __table_args__ = (
        UniqueConstraint('user_id', 'encrypted_proxy_url', name='_user_proxy_uc'),
    )

class TaskHistory(Base):
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    celery_task_id = Column(String, unique=True, nullable=True, index=True)
    task_name = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING", nullable=False, index=True)
    parameters = Column(JSON, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="task_history")
    __table_args__ = (
        Index('ix_task_history_user_status', 'user_id', 'status'),
    )

class Automation(Base):
    __tablename__ = "automations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_type = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=False, nullable=False)
    settings = Column(JSON, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="automations")
    __table_args__ = (
        UniqueConstraint('user_id', 'automation_type', name='_user_automation_uc'),
    )

class DailyStats(Base):
    __tablename__ = "daily_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    like_friends_feed_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    stories_viewed_count = Column(Integer, default=0, nullable=False)
    friends_removed_count = Column(Integer, default=0, nullable=False)
    messages_sent_count = Column(Integer, default=0, nullable=False)
    
    user = relationship("User", back_populates="daily_stats")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_uc'),
        Index('ix_daily_stats_user_date', 'user_id', 'date'),
    )

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    payment_system_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending", nullable=False)
    plan_name = Column(String, nullable=False)
    months = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = relationship("User")

class Scenario(Base):
    __tablename__ = "scenarios"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    schedule = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    
    user = relationship("User", back_populates="scenarios")
    steps = relationship("ScenarioStep", back_populates="scenario", cascade="all, delete-orphan", lazy="selectin", order_by="ScenarioStep.step_order")

class ScenarioStep(Base):
    __tablename__ = "scenario_steps"
    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    action_type = Column(String, nullable=False)
    settings = Column(JSON, nullable=False)
    batch_settings = Column(JSON, nullable=True) # <-- НОВОЕ ПОЛЕ
    scenario = relationship("Scenario", back_populates="steps")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String, nullable=False)
    level = Column(String, default="info", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    user = relationship("User", back_populates="notifications")

class ProfileMetric(Base):
    __tablename__ = "profile_metrics"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    total_likes_on_content = Column(Integer, nullable=False)
    friends_count = Column(Integer, nullable=False)

    user = relationship("User", back_populates="profile_metrics")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_metric_uc'),
        Index('ix_profile_metrics_user_date', 'user_id', 'date'),
    )

class WeeklyStats(Base):
    __tablename__ = "weekly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_identifier = Column(String, nullable=False)  # Например, '2024-35'
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'week_identifier', name='_user_week_uc'),
    )

class MonthlyStats(Base):
    __tablename__ = "monthly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month_identifier = Column(String, nullable=False) # Например, '2024-09'
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    
    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'month_identifier', name='_user_month_uc'),
    )

class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False) # e.g., 'SUCCESS', 'ERROR'
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    user = relationship("User")

class SentCongratulation(Base):
    __tablename__ = "sent_congratulations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_vk_id = Column(BigInteger, nullable=False, index=True)
    year = Column(Integer, nullable=False)

    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'friend_vk_id', 'year', name='_user_friend_year_uc'),
    )

class FriendsHistory(Base):
    __tablename__ = "friends_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    friends_count = Column(Integer, nullable=False)

    user = relationship("User")
    __table_args__ = (
        UniqueConstraint('user_id', 'date', name='_user_date_friends_uc'),
        Index('ix_friends_history_user_date', 'user_id', 'date'),
    )

# --- backend/app\db\scheduler_models.py ---

# backend/app/db/scheduler_models.py
"""
Этот файл содержит модели, необходимые для работы
библиотеки sqlalchemy-celery-beat.
Их нужно импортировать, чтобы Alembic мог их "увидеть"
и создать для них таблицы.
"""
# --- ИСПРАВЛЕНИЕ: Импорт из правильного, установленного пакета ---
from sqlalchemy_celery_beat.models import (
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
    SolarSchedule
)

__all__ = [
    'PeriodicTask',
    'IntervalSchedule',
    'CrontabSchedule',
    'SolarSchedule'
]

# --- backend/app\db\session.py ---

# backend/app/db/session.py

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool # <-- НОВЫЙ ИМПОРТ

from app.core.config import settings

engine = create_async_engine(
    settings.database_url, 
    pool_pre_ping=True, 
    poolclass=NullPool
)

# Создаем фабрику асинхронных сессий
AsyncSessionFactory = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Зависимость (dependency) для FastAPI, которая предоставляет сессию базы данных.
    Гарантирует, что сессия будет закрыта после завершения запроса.
    """
    async with AsyncSessionFactory() as session:
        yield session

# --- backend/app\db\__init__.py ---



# --- backend/app\repositories\base.py ---

# backend/app/repositories/base.py
from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository:
    """
    Базовый класс для всех репозиториев.
    Предоставляет общую зависимость от сессии базы данных.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, model, item_id: int):
        """
        Универсальный метод для получения объекта по его ID.
        """
        return await self.session.get(model, item_id)

# --- backend/app\repositories\stats.py ---

# backend/app/repositories/stats.py
import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyStats, User
from app.repositories.base import BaseRepository


class StatsRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_or_create_today_stats(self, user_id: int) -> DailyStats:
        """Получает или создает запись о статистике за сегодня для пользователя."""
        today = datetime.date.today()
        query = select(DailyStats).where(
            DailyStats.user_id == user_id, DailyStats.date == today
        )
        result = await self.session.execute(query)
        stats = result.scalar_one_or_none()

        if not stats:
            stats = DailyStats(user_id=user_id, date=today)
            self.session.add(stats)
            # Важно: коммит здесь не делаем, он будет сделан в конце всей операции в сервисе
            await self.session.flush()
            await self.session.refresh(stats)
        return stats

# --- backend/app\repositories\user.py ---

# backend/app/repositories/user.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def get_by_vk_id(self, vk_id: int) -> User | None:
        """Ищет пользователя по его VK ID."""
        query = select(User).where(User.vk_id == vk_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        """Создает нового пользователя."""
        new_user = User(**user_data)
        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)
        return new_user

    async def update(self, user: User, update_data: dict) -> User:
        """Обновляет данные пользователя."""
        for key, value in update_data.items():
            setattr(user, key, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

# --- backend/app\repositories\__init__.py ---



# --- backend/app\services\analytics_service.py ---

# backend/app/services/analytics_service.py
import datetime
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import FriendsHistory

class AnalyticsService(BaseVKService):

    async def snapshot_friends_count(self):
        await self._initialize_vk_api()
        
        user_info = await self.vk_api.get_user_info(user_ids=str(self.user.vk_id))
        if not user_info or 'counters' not in user_info:
            return

        friends_count = user_info['counters'].get('friends', 0)
        today = datetime.date.today()

        stmt = insert(FriendsHistory).values(
            user_id=self.user.id,
            date=today,
            friends_count=friends_count
        ).on_conflict_do_update(
            index_elements=['user_id', 'date'],
            set_={'friends_count': friends_count}
        )

        await self.db.execute(stmt)
        await self.db.commit()

# --- backend/app\services\automation_service.py ---

# backend/app/services/automation_service.py
import datetime
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.services.vk_api import VKAccessDeniedError
from app.db.models import SentCongratulation
from app.core.exceptions import InvalidActionSettingsError

class AutomationService(BaseVKService):

    async def congratulate_friends_with_birthday(self, **kwargs):
        settings = kwargs
        return await self._execute_logic(self._congratulate_friends_logic, settings)

    async def _congratulate_friends_logic(self, settings: dict):
        default_template = settings.get("message_template_default")
        male_template = settings.get("message_template_male", default_template)
        female_template = settings.get("message_template_female", default_template)

        if not default_template:
            raise InvalidActionSettingsError("Необходимо указать основной шаблон сообщения для поздравления.")

        await self.emitter.send_log("Запуск задачи: Поздравление друзей с Днем Рождения.", "info")
        
        friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="bdate,sex")
        if not friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return

        today = datetime.date.today()
        today_str = f"{today.day}.{today.month}"
        
        birthday_friends = [
            f for f in friends 
            if f.get("bdate") and f.get("bdate").startswith(today_str)
        ]

        if not birthday_friends:
            await self.emitter.send_log("Сегодня нет дней рождения у друзей.", "info")
            return

        await self.emitter.send_log(f"Найдено именинников: {len(birthday_friends)} чел. Начинаем поздравлять.", "info")

        current_year = today.year
        stmt = select(SentCongratulation.friend_vk_id).where(
            and_(
                SentCongratulation.user_id == self.user.id,
                SentCongratulation.year == current_year
            )
        )
        result = await self.db.execute(stmt)
        already_congratulated_ids = {row[0] for row in result.all()}

        processed_count = 0
        for friend in birthday_friends:
            friend_id = friend['id']
            if friend_id in already_congratulated_ids:
                continue

            name = friend.get("first_name", "")
            sex = friend.get("sex")

            if sex == 2:
                message_template = male_template
            elif sex == 1:
                message_template = female_template
            else:
                message_template = default_template

            message = message_template.replace("{name}", name)
            url = f"https://vk.com/id{friend_id}"

            await self.humanizer.imitate_simple_action()

            try:
                result = await self.vk_api.send_message(friend_id, message)
                if result:
                    insert_stmt = insert(SentCongratulation).values(
                        user_id=self.user.id,
                        friend_vk_id=friend_id,
                        year=current_year
                    ).on_conflict_do_nothing()
                    await self.db.execute(insert_stmt)
                    
                    await self.emitter.send_log(f"Успешно отправлено поздравление для {name}", "success", target_url=url)
                    processed_count += 1
                else:
                    await self.emitter.send_log(f"Не удалось отправить поздравление для {name}. Ответ VK: {result}", "error", target_url=url)

            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить сообщение для {name} (профиль закрыт или ЧС).", "warning", target_url=url)
        
        await self.emitter.send_log(f"Задача завершена. Отправлено поздравлений: {processed_count}.", "success")
        
    async def set_online_status(self, **kwargs):
        return await self._execute_logic(self._set_online_status_logic)

    async def _set_online_status_logic(self):
        await self.emitter.send_log("Поддержание статуса 'онлайн'...", "debug")
        await self.vk_api.set_online()
        await self.emitter.send_log("Статус 'онлайн' успешно обновлен.", "success")

# --- backend/app\services\base.py ---

# backend/app/services/base.py
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.db.models import User, DailyStats, Proxy
from app.services.vk_api import VKAPI
from app.services.humanizer import Humanizer
from app.services.event_emitter import RedisEventEmitter
from app.repositories.stats import StatsRepository
from app.core.security import decrypt_data

class BaseVKService:
    def __init__(
        self,
        db: AsyncSession,
        user: User,
        emitter: RedisEventEmitter,
    ):
        self.db = db
        self.user = user
        self.emitter = emitter
        self.stats_repo = StatsRepository(db)
        self.vk_api: VKAPI | None = None
        self.humanizer: Humanizer | None = None

    async def _initialize_vk_api(self):
        if self.vk_api:
            return

        vk_token = decrypt_data(self.user.encrypted_vk_token)
        proxy_url = await self._get_working_proxy()
        
        self.vk_api = VKAPI(access_token=vk_token, proxy=proxy_url)
        self.humanizer = Humanizer(delay_profile=self.user.delay_profile, logger_func=self.emitter.send_log)

    async def _get_working_proxy(self) -> str | None:
        if 'proxies' not in self.user.__dict__:
             stmt = select(User).where(User.id == self.user.id).options(selectinload(User.proxies))
             result = await self.db.execute(stmt)
             self.user = result.scalar_one()

        working_proxies = [p for p in self.user.proxies if p.is_working]
        if not working_proxies:
            return None
        
        chosen_proxy = random.choice(working_proxies)
        return decrypt_data(chosen_proxy.encrypted_proxy_url)

    async def _get_today_stats(self) -> DailyStats:
        return await self.stats_repo.get_or_create_today_stats(self.user.id)

    async def _increment_stat(self, stats: DailyStats, field_name: str, value: int = 1):
        current_value = getattr(stats, field_name)
        new_value = current_value + value
        setattr(stats, field_name, new_value)
        await self.emitter.send_stats_update({field_name: new_value})

    async def _execute_logic(self, logic_func, *args, **kwargs):
        await self._initialize_vk_api()
        
        try:
            result = await logic_func(*args, **kwargs)
            await self.db.commit()
            return result
        except Exception as e:
            await self.db.rollback()
            await self.emitter.send_log(f"Произошла ошибка, все изменения отменены: {type(e).__name__} - {e}", status="error")
            raise

# --- backend/app\services\event_emitter.py ---

# backend/app/services/event_emitter.py
import datetime
import json
from typing import Literal, Dict, Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Notification, TaskHistory

LogLevel = Literal["debug", "info", "success", "warning", "error"]

class RedisEventEmitter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.user_id = None
        self.task_history_id = None

    def set_context(self, user_id: int, task_history_id: int | None = None):
        self.user_id = user_id
        self.task_history_id = task_history_id

    async def _publish(self, channel: str, message: Dict[str, Any]):
        if not self.user_id:
            raise ValueError("User ID must be set before emitting events.")
        await self.redis.publish(channel, json.dumps(message))

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        payload = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "message": message,
            "status": status,
            "url": target_url,
            "task_history_id": self.task_history_id,
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "log", "payload": payload})

    async def send_stats_update(self, stats_dict: Dict[str, Any]):
        await self._publish(f"ws:user:{self.user_id}", {"type": "stats_update", "payload": stats_dict})

    async def send_task_status_update(self, status: str, result: str | None = None, task_name: str | None = None, created_at: datetime.datetime | None = None):
        if not self.task_history_id: return
        
        payload = {
            "task_history_id": self.task_history_id, 
            "status": status, 
            "result": result,
            "task_name": task_name,
            "created_at": created_at.isoformat() if created_at else None
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "task_history_update", "payload": payload})

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        new_notification = Notification(user_id=self.user_id, message=message, level=level)
        db.add(new_notification)
        await db.flush()
        await db.refresh(new_notification)

        payload = {
            "id": new_notification.id,
            "message": new_notification.message,
            "level": new_notification.level,
            "is_read": new_notification.is_read,
            "created_at": new_notification.created_at.isoformat()
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "new_notification", "payload": payload})

# --- backend/app\services\feed_service.py ---

# backend/app/services/feed_service.py
import random
from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError

class FeedService(BaseVKService):

    async def like_newsfeed(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._like_newsfeed_logic, count, filters)

    async def _like_newsfeed_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Запуск задачи: поставить {count} лайков в ленте новостей.", "info")
        stats = await self._get_today_stats()
        filters['allow_closed_profiles'] = True

        await self.humanizer.imitate_page_view()
        response = await self.vk_api.get_newsfeed(count=count * 2)

        if not response or not response.get('items'):
            await self.emitter.send_log("Посты в ленте не найдены.", "warning")
            return

        posts = [p for p in response['items'] if p.get('type') == 'post']
        author_ids = [abs(p['source_id']) for p in posts if p.get('source_id') and p['source_id'] > 0]
        filtered_author_ids = set(author_ids)

        if author_ids:
            author_profiles = await self._get_user_profiles(list(set(author_ids)))
            filtered_authors = self._apply_filters_to_profiles(author_profiles, filters)
            filtered_author_ids = {a['id'] for a in filtered_authors}

        processed_count = 0
        for post in posts:
            if processed_count >= count:
                break
            if stats.likes_count >= self.user.daily_likes_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит лайков ({self.user.daily_likes_limit}).")

            owner_id = post.get('source_id')
            if not owner_id or post.get('likes', {}).get('user_likes') == 1:
                continue
            if owner_id > 0 and owner_id not in filtered_author_ids:
                continue

            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.add_like('post', owner_id, post['post_id'])
            
            if result and 'likes' in result:
                processed_count += 1
                await self._increment_stat(stats, 'likes_count')
                if processed_count % 10 == 0:
                     await self.emitter.send_log(f"Поставлено лайков: {processed_count}/{count}", "info")
            else:
                url = f"https://vk.com/wall{owner_id}_{post['post_id']}"
                await self.emitter.send_log(f"Не удалось поставить лайк. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков: {processed_count}.", "success")

    async def like_friends_feed(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._like_friends_feed_logic, count, filters)

    async def _like_friends_feed_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Запуск задачи: поставить {count} лайков на стенах друзей.", "info")
        stats = await self._get_today_stats()
        filters['allow_closed_profiles'] = True

        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen")
        if not friends_response:
            await self.emitter.send_log("Не удалось получить список друзей.", "error")
            return

        filtered_friends = self._apply_filters_to_profiles(friends_response, filters)
        if not filtered_friends:
            await self.emitter.send_log("После применения фильтров не осталось друзей для обработки.", "warning")
            return

        processed_likes = 0
        random.shuffle(filtered_friends)
        for friend in filtered_friends:
            if processed_likes >= count:
                break
            if stats.likes_count >= self.user.daily_likes_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит лайков ({self.user.daily_likes_limit}).")

            friend_id = friend['id']
            await self.humanizer.imitate_page_view()
            wall = await self.vk_api.get_wall(owner_id=friend_id, count=5)
            if not wall or not wall.get('items'):
                continue

            posts_to_like = [p for p in wall['items'] if p.get('likes', {}).get('user_likes') == 0]
            if not posts_to_like:
                continue

            post_to_like = random.choice(posts_to_like)
            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.add_like('post', friend_id, post_to_like['id'])
            
            if result and 'likes' in result:
                processed_likes += 1
                await self._increment_stat(stats, 'likes_count')
                await self._increment_stat(stats, 'like_friends_feed_count')
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/wall{friend_id}_{post_to_like['id']}"
                await self.emitter.send_log(f"Поставлен лайк другу {name} ({processed_likes}/{count})", "success", target_url=url)
            else:
                url = f"https://vk.com/wall{friend_id}_{post_to_like['id']}"
                await self.emitter.send_log(f"Не удалось поставить лайк другу. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков друзьям: {processed_likes}.", "success")
        
    async def _get_user_profiles(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        if not user_ids:
            return []
        user_profiles = []
        for i in range(0, len(user_ids), 1000):
            chunk = user_ids[i:i + 1000]
            ids_str = ",".join(map(str, chunk))
            profiles = await self.vk_api.get_user_info(user_ids=ids_str)
            if profiles:
                user_profiles.extend(profiles)
        return user_profiles

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()

        for profile in profiles:
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True):
                continue
            
            if filters.get('sex') and profile.get('sex') != filters['sex']:
                continue
            
            if filters.get('is_online', False) and not profile.get('online', 0):
                continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts == 0:
                continue

            last_seen_days = filters.get('last_seen_days')
            if last_seen_days and (now_ts - last_seen_ts) > (last_seen_days * 86400):
                continue

            filtered_profiles.append(profile)
            
        return filtered_profiles

# --- backend/app\services\friend_management_service.py ---

# backend/app/services/friend_management_service.py
import asyncio
from typing import Dict, Any, List
from app.services.base import BaseVKService

class FriendManagementService(BaseVKService):

    async def remove_friends_by_criteria(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._remove_friends_by_criteria_logic, count, filters)

    async def _remove_friends_by_criteria_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Начинаем чистку друзей. Цель: удалить {count} чел.", "info")
        stats = await self._get_today_stats()

        all_friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,is_closed,deactivated")
        if not all_friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return

        banned_friends = [f for f in all_friends if f.get('deactivated') in ['banned', 'deleted']]
        active_friends = [f for f in all_friends if not f.get('deactivated')]
        
        if not filters.get('remove_banned', True):
            banned_friends = []
        
        await self.emitter.send_log(f"Найдено забаненных/удаленных друзей: {len(banned_friends)}.", "info")
        
        filtered_active_friends = self._apply_filters_to_profiles(active_friends, filters)
        await self.emitter.send_log(f"Найдено друзей по критериям неактивности/пола: {len(filtered_active_friends)}.", "info")
        
        friends_to_remove = (banned_friends + filtered_active_friends)[:count]
        if not friends_to_remove:
            await self.emitter.send_log("Друзей для удаления по заданным критериям не найдено.", "success")
            return

        await self.emitter.send_log(f"Всего к удалению: {len(friends_to_remove)} чел. Начинаем процесс...", "info")
        processed_count = 0
        
        batch_size = 25
        for i in range(0, len(friends_to_remove), batch_size):
            batch = friends_to_remove[i:i + batch_size]
            
            calls = [
                {"method": "friends.delete", "params": {"user_id": friend['id']}}
                for friend in batch
            ]
            
            await self.humanizer.imitate_simple_action()
            
            results = await self.vk_api.execute(calls)
            
            if results is None:
                await self.emitter.send_log(f"Пакетный запрос на удаление не удался.", "error")
                continue

            for friend, result in zip(batch, results):
                user_id = friend['id']
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"

                if result and result.get('success') == 1:
                    processed_count += 1
                    await self._increment_stat(stats, 'friends_removed_count')
                    reason = f"({friend.get('deactivated', 'неактивность')})"
                    await self.emitter.send_log(f"Удален друг: {name} {reason}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', 'неизвестная ошибка') if isinstance(result, dict) else 'неизвестная ошибка'
                    await self.emitter.send_log(f"Не удалось удалить друга {name}. Причина: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Чистка завершена. Удалено друзей: {processed_count}.", "success")

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()
        for profile in profiles:
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True): continue
            if filters.get('sex') and profile.get('sex') != filters['sex']: continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts == 0: continue
            
            last_seen_days = filters.get('last_seen_days')
            if last_seen_days and (now_ts - last_seen_ts) > (last_seen_days * 86400):
                filtered_profiles.append(profile)
                continue

        return filtered_profiles

# --- backend/app\services\group_management_service.py ---

# backend/app/services/group_management_service.py
from typing import Dict, Any
import asyncio
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError

class GroupManagementService(BaseVKService):

    async def leave_groups_by_criteria(self, count: int, filters: Dict[str, Any], **kwargs):
        return await self._execute_logic(self._leave_groups_logic, count, filters)

    async def _leave_groups_logic(self, count: int, filters: Dict[str, Any]):
        await self.emitter.send_log(f"Запуск задачи: отписаться от {count} сообществ.", "info")
        stats = await self._get_today_stats()

        response = await self.vk_api.get_groups(user_id=self.user.vk_id)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не удалось получить список сообществ.", "warning")
            return
        
        all_groups = response['items']
        
        groups_to_leave = []
        keyword = filters.get('status_keyword', '').lower().strip()

        if keyword:
            groups_to_leave = [
                group for group in all_groups if keyword in group.get('name', '').lower()
            ]
            await self.emitter.send_log(f"Найдено {len(groups_to_leave)} сообществ по ключевому слову '{keyword}'.", "info")
        else:
            groups_to_leave = all_groups # Если нет ключевого слова, отписываемся от всех подряд
        
        if not groups_to_leave:
            await self.emitter.send_log("Сообществ для отписки по заданным критериям не найдено.", "success")
            return

        groups_to_leave = groups_to_leave[:count]
        
        processed_count = 0
        for group in groups_to_leave:
            group_id = group['id']
            group_name = group['name']
            url = f"https://vk.com/public{group_id}"
            
            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.leave_group(group_id)

            if result == 1:
                processed_count += 1
                # Можно добавить новую колонку в DailyStats для отписок, если нужно
                await self.emitter.send_log(f"Вы успешно покинули сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось покинуть сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Покинуто сообществ: {processed_count}.", "success")

# --- backend/app\services\humanizer.py ---

# backend/app/services/humanizer.py
import asyncio
import random
from typing import Callable, Awaitable
from app.db.models import DelayProfile
import structlog

log = structlog.get_logger(__name__)

DELAY_CONFIG = {
    DelayProfile.fast: {
        "page_load": (0.8, 1.5),
        "scroll": (0.5, 1.2),
        "action_decision": (0.7, 1.3),
        "short_action": (0.6, 1.1),
    },
    DelayProfile.normal: {
        "page_load": (1.5, 3.0),
        "scroll": (1.0, 2.5),
        "action_decision": (1.2, 2.8),
        "short_action": (1.0, 2.0),
    },
    DelayProfile.slow: {
        "page_load": (3.0, 5.5),
        "scroll": (2.5, 4.0),
        "action_decision": (2.8, 5.0),
        "short_action": (2.0, 3.5),
    },
}

class Humanizer:
    def __init__(self, delay_profile: DelayProfile, logger_func: Callable[..., Awaitable[None]]):
        self.profile = DELAY_CONFIG.get(delay_profile, DELAY_CONFIG[DelayProfile.normal])
        self._log = logger_func
        self.session_multiplier = random.uniform(0.9, 1.1)

    async def _sleep(self, min_sec: float, max_sec: float, log_message: str | None = None):
        delay = random.uniform(min_sec, max_sec) * self.session_multiplier
        if log_message:
            await self._log(f"{log_message} (пауза ~{delay:.1f} сек.)", status="debug")
        await asyncio.sleep(delay)

    async def imitate_page_view(self):
        load_min, load_max = self.profile["page_load"]
        await self._sleep(load_min, load_max, "Имитация загрузки страницы...")
        
        if random.random() < 0.7:
            scroll_min, scroll_max = self.profile["scroll"]
            scroll_times = random.randint(1, 4)
            
            if scroll_times > 0:
                await self._log(f"Имитация скроллинга ({scroll_times} раз)...", status="debug")
                for _ in range(scroll_times):
                    await self._sleep(scroll_min * 0.8, scroll_max * 1.2)
            
        decision_min, decision_max = self.profile["action_decision"]
        await self._sleep(decision_min, decision_max, "Пауза перед действием...")

    async def imitate_simple_action(self):
        if random.random() < 0.3:
            await self._sleep(0.3, 0.8)

        action_min, action_max = self.profile["short_action"]
        await self._sleep(action_min, action_max)

# --- backend/app\services\incoming_request_service.py ---

# backend/app/services/incoming_request_service.py
from typing import Dict, Any, List
from app.services.base import BaseVKService

class IncomingRequestService(BaseVKService):
    async def accept_friend_requests(self, **kwargs):
        filters: Dict[str, Any] = kwargs.get('filters', {})
        return await self._execute_logic(self._accept_friend_requests_logic, filters)

    async def _accept_friend_requests_logic(self, filters: Dict[str, Any]):
        await self.emitter.send_log("Начинаем прием заявок в друзья...", "info")
        stats = await self._get_today_stats()
        
        response = await self.vk_api.get_incoming_friend_requests(extended=1)
        if not response or not response.get('items'):
            await self.emitter.send_log("Входящие заявки не найдены.", "info")
            return
        
        profiles = response['items']
        await self.emitter.send_log(f"Найдено {len(profiles)} заявок. Начинаем фильтрацию...", "info")
        
        filtered_profiles = self._apply_filters_to_profiles(profiles, filters)

        await self.emitter.send_log(f"После фильтрации осталось: {len(filtered_profiles)}.", "info")
        
        if not filtered_profiles:
            await self.emitter.send_log("Подходящих заявок для приема не найдено.", "success")
            return
        
        processed_count = 0
        batch_size = 25
        for i in range(0, len(filtered_profiles), batch_size):
            batch = filtered_profiles[i:i + batch_size]
            
            calls = [
                {"method": "friends.add", "params": {"user_id": profile['id']}}
                for profile in batch
            ]

            await self.humanizer.imitate_simple_action()
            results = await self.vk_api.execute(calls)

            if results is None:
                await self.emitter.send_log(f"Пакетный запрос на принятие заявок не удался.", "error")
                continue

            for profile, result in zip(batch, results):
                user_id = profile['id']
                name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"
                
                if result in [1, 2, 4]:
                    processed_count += 1
                    await self._increment_stat(stats, 'friend_requests_accepted_count')
                    await self.emitter.send_log(f"Принята заявка от {name}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', 'неизвестная ошибка') if isinstance(result, dict) else f'код {result}'
                    await self.emitter.send_log(f"Не удалось принять заявку от {name}. Ответ VK: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Завершено. Принято заявок: {processed_count}.", "success")

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()
        for profile in profiles:
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True): continue
            if filters.get('sex') is not None and filters.get('sex') != 0 and profile.get('sex') != filters['sex']: continue
            if filters.get('is_online', False) and not profile.get('online', 0): continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts:
                last_seen_hours = filters.get('last_seen_hours')
                if last_seen_hours and (now_ts - last_seen_ts) > (last_seen_hours * 3600):
                    continue

            counters = profile.get('counters', {})
            friends_count = counters.get('friends', 0)
            followers_count = counters.get('followers', 0)

            # --- ИЗМЕНЕНИЕ: Добавлена логика для min/max ---
            min_friends = filters.get('min_friends')
            if min_friends is not None and min_friends > 0 and friends_count < min_friends:
                continue
            
            max_friends = filters.get('max_friends')
            if max_friends is not None and max_friends > 0 and friends_count > max_friends:
                continue
                
            min_followers = filters.get('min_followers')
            if min_followers is not None and min_followers > 0 and followers_count < min_followers:
                continue

            max_followers = filters.get('max_followers')
            if max_followers is not None and max_followers > 0 and followers_count > max_followers:
                continue
            
            filtered_profiles.append(profile)
            
        return filtered_profiles

# --- backend/app\services\message_service.py ---

# backend/app/services/message_service.py
from typing import Dict, Any, List
import random
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError, InvalidActionSettingsError
from app.services.vk_api import VKAccessDeniedError

class MessageService(BaseVKService):

    async def send_mass_message(self, count: int, filters: Dict[str, Any], message_text: str, only_new_dialogs: bool, **kwargs):
        return await self._execute_logic(self._send_mass_message_logic, count, filters, message_text, only_new_dialogs)

    async def _send_mass_message_logic(self, count: int, filters: Dict[str, Any], message_text: str, only_new_dialogs: bool):
        if not message_text or not message_text.strip():
            raise InvalidActionSettingsError("Текст сообщения не может быть пустым.")

        await self.emitter.send_log(f"Запуск массовой рассылки. Цель: {count} сообщений.", "info")
        stats = await self._get_today_stats()

        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen")
        if not friends_response:
            await self.emitter.send_log("Не удалось получить список друзей.", "error")
            return

        filtered_friends = self._apply_filters_to_profiles(friends_response, filters)
        if not filtered_friends:
            await self.emitter.send_log("После применения фильтров не осталось друзей для рассылки.", "warning")
            return

        await self.emitter.send_log(f"Найдено друзей по фильтрам: {len(filtered_friends)}. Начинаем обработку.", "info")
        random.shuffle(filtered_friends)
        
        target_friends = []
        if only_new_dialogs:
            dialogs = await self.vk_api.get_conversations(count=200)
            dialog_peer_ids = {conv['conversation']['peer']['id'] for conv in dialogs.get('items', [])}
            target_friends = [f for f in filtered_friends if f['id'] not in dialog_peer_ids]
            await self.emitter.send_log(f"Режим 'Только новые диалоги'. Осталось целей: {len(target_friends)}.", "info")
        else:
            target_friends = filtered_friends
        
        if not target_friends:
            await self.emitter.send_log("Не найдено подходящих получателей.", "success")
            return
            
        processed_count = 0
        for friend in target_friends:
            if processed_count >= count:
                break

            friend_id = friend['id']
            name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
            url = f"https://vk.com/id{friend_id}"
            
            final_message = message_text.replace("{name}", friend.get('first_name', ''))

            await self.humanizer.imitate_page_view()

            try:
                result = await self.vk_api.send_message(friend_id, final_message)
                if result:
                    processed_count += 1
                    await self._increment_stat(stats, 'messages_sent_count')
                    await self.emitter.send_log(f"Сообщение для {name} успешно отправлено.", "success", target_url=url)
                else:
                    await self.emitter.send_log(f"Не удалось отправить сообщение для {name}. Ответ VK: {result}", "error", target_url=url)
            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить сообщение (профиль закрыт или ЧС): {name}", "warning", target_url=url)
            except Exception as e:
                await self.emitter.send_log(f"Ошибка при отправке сообщения для {name}: {e}", "error", target_url=url)

        await self.emitter.send_log(f"Рассылка завершена. Отправлено сообщений: {processed_count}.", "success")

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()

        for profile in profiles:
            if filters.get('sex') is not None and filters.get('sex') != 0 and profile.get('sex') != filters['sex']:
                continue
            if filters.get('is_online', False) and not profile.get('online', 0):
                continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts:
                last_seen_hours = filters.get('last_seen_hours')
                if last_seen_hours and (now_ts - last_seen_ts) > (last_seen_hours * 3600):
                    continue
            
            filtered_profiles.append(profile)
        return filtered_profiles

# --- backend/app\services\outgoing_request_service.py ---

# backend/app/services/outgoing_request_service.py
from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.db.models import DailyStats
from app.core.exceptions import UserLimitReachedError
from app.core.config import settings
from redis.asyncio import Redis as AsyncRedis

redis_lock_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)

class OutgoingRequestService(BaseVKService):
    async def add_recommended_friends(self, count: int, filters: Dict[str, Any], like_config: Dict[str, Any], send_message_on_add: bool, message_text: str | None, **kwargs):
        return await self._execute_logic(self._add_recommended_friends_logic, count, filters, like_config, send_message_on_add, message_text)

    async def _add_recommended_friends_logic(self, count: int, filters: Dict[str, Any], like_config: Dict[str, Any], send_message_on_add: bool, message_text: str | None):
        await self.emitter.send_log(f"Начинаем добавление {count} друзей из рекомендаций...", "info")
        stats = await self._get_today_stats()
        
        response = await self.vk_api.get_recommended_friends(count=count * 3)
        if not response or not response.get('items'):
            await self.emitter.send_log("Рекомендации не найдены.", "warning")
            return

        filtered_profiles = self._apply_filters_to_profiles(response['items'], filters)
        await self.emitter.send_log(f"Найдено {len(response['items'])} рекомендаций. После фильтрации осталось: {len(filtered_profiles)}.", "info")
        
        processed_count = 0
        for profile in filtered_profiles:
            if processed_count >= count: break
            if stats.friends_added_count >= self.user.daily_add_friends_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит на отправку заявок ({self.user.daily_add_friends_limit}).")
            
            user_id = profile['id']
            
            lock_key = f"lock:add_friend:{self.user.id}:{user_id}"
            if not await redis_lock_client.set(lock_key, "1", ex=3600, nx=True):
                await self.emitter.send_log(f"Заявка пользователю {user_id} уже была отправлена недавно. Пропуск.", "debug")
                continue

            await self.humanizer.imitate_page_view()
            
            message = message_text.replace("{name}", profile.get("first_name", "")) if message_text else None
            result = await self.vk_api.add_friend(user_id, message if send_message_on_add else None) 
            
            name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
            url = f"https://vk.com/id{user_id}"
            
            if result in [1, 2, 4]:
                processed_count += 1
                await self._increment_stat(stats, 'friends_added_count')
                log_msg = f"Отправлена заявка пользователю {name}"
                if send_message_on_add and message_text:
                    log_msg += " с сообщением."
                await self.emitter.send_log(log_msg, "success", target_url=url)
                
                if like_config.get('enabled') and not profile.get('is_closed', True):
                    await self._like_user_content(user_id, profile, like_config, stats)
            else:
                await self.emitter.send_log(f"Не удалось отправить заявку {name}. Ответ VK: {result}", "error", target_url=url)
                await redis_lock_client.delete(lock_key)

        await self.emitter.send_log(f"Завершено. Отправлено заявок: {processed_count}.", "success")

    async def _like_user_content(self, user_id: int, profile: Dict[str, Any], config: Dict[str, Any], stats: DailyStats):
        if stats.likes_count >= self.user.daily_likes_limit:
            await self.emitter.send_log("Достигнут дневной лимит лайков, пропуск лайкинга после добавления.", "warning")
            return

        targets = config.get('targets', [])
        
        if 'avatar' in targets and profile.get('photo_id'):
            photo_id_parts = profile['photo_id'].split('_')
            if len(photo_id_parts) == 2:
                photo_id = int(photo_id_parts[1])
                await self.humanizer.imitate_simple_action()
                res = await self.vk_api.add_like('photo', user_id, photo_id)
                if res and 'likes' in res:
                    await self._increment_stat(stats, 'likes_count')
                    await self.emitter.send_log(f"Поставлен лайк на аватар.", "success", target_url=f"https://vk.com/photo{user_id}_{photo_id}")

        if 'wall' in targets:
            wall = await self.vk_api.get_wall(owner_id=user_id, count=config.get('count', 1))
            if wall and wall.get('items'):
                for post in wall['items']:
                    if stats.likes_count >= self.user.daily_likes_limit: return
                    await self.humanizer.imitate_simple_action()
                    res = await self.vk_api.add_like('post', user_id, post['id'])
                    if res and 'likes' in res:
                        await self._increment_stat(stats, 'likes_count')
                        await self.emitter.send_log(f"Поставлен лайк на пост на стене.", "success", target_url=f"https://vk.com/wall{user_id}_{post['id']}")

    def _apply_filters_to_profiles(self, profiles: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        import datetime
        filtered_profiles = []
        now_ts = datetime.datetime.now().timestamp()
        for profile in profiles:
            if not filters.get('allow_closed_profiles', False) and profile.get('is_closed', True): continue
            if filters.get('sex') is not None and filters.get('sex') != 0 and profile.get('sex') != filters['sex']: continue
            if filters.get('is_online', False) and not profile.get('online', 0): continue
            
            last_seen_ts = profile.get('last_seen', {}).get('time', 0)
            if last_seen_ts:
                last_seen_hours = filters.get('last_seen_hours')
                if last_seen_hours and (now_ts - last_seen_ts) > (last_seen_hours * 3600):
                    continue
            
            filtered_profiles.append(profile)
        return filtered_profiles

# --- backend/app\services\profile_analytics_service.py ---

# backend/app/services/profile_analytics_service.py
import datetime
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import ProfileMetric
from app.services.vk_api import VKAPIError
import structlog

log = structlog.get_logger(__name__)

class ProfileAnalyticsService(BaseVKService):

    async def snapshot_profile_metrics(self):
        try:
            await self._initialize_vk_api()
        except Exception as e:
            log.error("snapshot_metrics.init_failed", user_id=self.user.id, error=str(e))
            return

        total_likes = 0
        try:
            wall_posts = await self.vk_api.get_wall(owner_id=self.user.vk_id, count=100)
            if wall_posts and wall_posts.get('items'):
                total_likes += sum(post.get('likes', {}).get('count', 0) for post in wall_posts['items'])

            photos = await self.vk_api.get_photos(owner_id=self.user.vk_id, count=200)
            if photos and photos.get('items'):
                total_likes += sum(photo.get('likes', {}).get('count', 0) for photo in photos['items'])
        except VKAPIError as e:
            log.warn("snapshot_metrics.likes_error", user_id=self.user.id, error=str(e))

        friends_count = 0
        try:
            user_info = await self.vk_api.get_user_info(user_ids=str(self.user.vk_id))
            if user_info and 'counters' in user_info:
                friends_count = user_info['counters'].get('friends', 0)
        except VKAPIError as e:
            log.error("snapshot_metrics.friends_error", user_id=self.user.id, error=str(e))
            return

        today = datetime.date.today()
        stmt = insert(ProfileMetric).values(
            user_id=self.user.id,
            date=today,
            total_likes_on_content=total_likes,
            friends_count=friends_count
        ).on_conflict_do_update(
            index_elements=['user_id', 'date'],
            set_={
                'total_likes_on_content': total_likes,
                'friends_count': friends_count
            }
        )
        await self.db.execute(stmt)
        await self.db.commit()
        log.info("snapshot_metrics.success", user_id=self.user.id, likes=total_likes, friends=friends_count)

# --- backend/app\services\proxy_service.py ---

# backend/app/services/proxy_service.py
import aiohttp
import asyncio
from typing import Tuple

class ProxyService:
    @staticmethod
    async def check_proxy(proxy_url: str) -> Tuple[bool, str]:
        if not proxy_url:
            return False, "URL прокси не может быть пустым."

        test_url = "https://api.vk.com/method/utils.getServerTime"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, proxy=proxy_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "response" in data:
                            return True, "Прокси успешно работает."
                    
                    return False, f"Сервер ответил с кодом: {response.status}"

        except aiohttp.ClientProxyConnectionError as e:
            return False, f"Ошибка подключения к прокси: {e}"
        except aiohttp.ClientError as e:
            return False, f"Сетевая ошибка: {e}"
        except asyncio.TimeoutError:
            return False, "Тайм-аут подключения (10 секунд)."
        except Exception as e:
            return False, f"Неизвестная ошибка: {e}"

# --- backend/app\services\story_service.py ---

# backend/app/services/story_service.py
from typing import Dict, Any
from app.services.base import BaseVKService

class StoryService(BaseVKService):

    async def view_stories(self, **kwargs):
        return await self._execute_logic(self._view_stories_logic)

    async def _view_stories_logic(self):
        await self.humanizer.imitate_page_view()
        await self.emitter.send_log("Начинаем просмотр историй...", "info")
        stats = await self._get_today_stats()

        response = await self.vk_api.get_stories()
        if not response or not response.get('items'):
            await self.emitter.send_log("Новых историй не найдено.", "info")
            return
        
        total_stories_count = sum(len(group.get('stories', [])) for group in response['items'])
        if total_stories_count == 0:
            await self.emitter.send_log("Новых историй не найдено.", "info")
            return

        await self.emitter.send_log(f"Найдено {total_stories_count} новых историй.", "info")
        await self._increment_stat(stats, 'stories_viewed_count', total_stories_count)
        await self.emitter.send_log(f"Успешно просмотрено {total_stories_count} историй.", "success")

# --- backend/app\services\vk_api.py ---

# backend/app/services/vk_api.py
import aiohttp
import random
import json
from typing import Optional, Dict, Any, List
from app.core.config import settings

class VKAPIError(Exception):
    def __init__(self, message: str, error_code: int):
        self.message = message
        self.error_code = error_code
        super().__init__(f"VK API Error [{self.error_code}]: {self.message}")

class VKRateLimitError(VKAPIError): pass
class VKInvalidTokenError(VKAPIError): pass
class VKAccessDeniedError(VKAPIError): pass
class VKAuthError(VKAPIError): pass

class VKAPI:
    def __init__(self, access_token: str, proxy: Optional[str] = None):
        self.access_token = access_token
        self.proxy = proxy
        self.api_version = settings.VK_API_VERSION
        self.base_url = "https://api.vk.com/method/"

    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if params is None:
            params = {}
        
        params['access_token'] = self.access_token
        params['v'] = self.api_version

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}{method}", data=params, proxy=self.proxy, timeout=20) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if 'error' in data:
                        error_data = data['error']
                        error_code = error_data.get('error_code')
                        error_msg = error_data.get('error_msg', 'Unknown VK error')
                        
                        if error_code == 5: raise VKAuthError(error_msg, error_code)
                        elif error_code == 6: raise VKRateLimitError(error_msg, error_code)
                        elif error_code in [15, 18, 203, 902]: raise VKAccessDeniedError(error_msg, error_code)
                        else: raise VKAPIError(error_msg, error_code)

                    return data.get('response')
            except aiohttp.ClientError as e:
                raise VKAPIError(f"HTTP Request failed: {e}", 0)

    async def execute(self, calls: List[Dict[str, Any]]) -> Optional[List[Any]]:
        if not 25 >= len(calls) > 0:
            raise ValueError("Number of calls for execute method must be between 1 and 25.")

        code_lines = [f'API.{call["method"]}({json.dumps(call.get("params", {}), ensure_ascii=False)})' for call in calls]
        code = f"return [{','.join(code_lines)}];"
        
        return await self._make_request("execute", params={"code": code})

    async def get_user_info(self, user_ids: Optional[str] = None, fields: Optional[str] = "photo_200,sex,online,last_seen,is_closed,status,counters,photo_id") -> Optional[Any]:
        params = {'fields': fields}
        if user_ids:
            params['user_ids'] = user_ids
        response = await self._make_request("users.get", params=params)
        if response and isinstance(response, list):
            return response[0] if user_ids is None and len(response) == 1 else response
        return None
    
    async def get_user_friends(self, user_id: int, fields: str = "sex,bdate,city,online,last_seen,is_closed,deactivated") -> Optional[List[Dict[str, Any]]]:
        params = {"user_id": user_id, "fields": fields}
        response = await self._make_request("friends.get", params=params)
        return response.get("items") if response else None

    async def add_friend(self, user_id: int, text: Optional[str] = None) -> Optional[Dict[str, Any]]:
        params = {"user_id": user_id}
        if text:
            params["text"] = text
        return await self._make_request("friends.add", params=params)

    async def get_wall(self, owner_id: int, count: int = 5) -> Optional[Dict[str, Any]]:
        return await self._make_request("wall.get", params={"owner_id": owner_id, "count": count})

    async def get_stories(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("stories.get", params={})

    async def get_incoming_friend_requests(self, count: int = 1000, **kwargs) -> Optional[Dict[str, Any]]:
        # --- ИСПРАВЛЕНИЕ: Убираем need_viewed, используем extended для получения профилей ---
        params = {"count": count, **kwargs}
        if 'extended' in params and params['extended'] == 1:
            params['fields'] = "sex,online,last_seen,is_closed,status,counters"
        return await self._make_request("friends.getRequests", params=params)

    async def accept_friend_request(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self._make_request("friends.add", params={"user_id": user_id})

    async def get_recommended_friends(self, count: int = 100) -> Optional[Dict[str, Any]]:
        return await self._make_request("friends.getSuggestions", params={"count": count, "filter": "mutual"})
        
    async def get_newsfeed(self, count: int = 100) -> Optional[Dict[str, Any]]:
        return await self._make_request("newsfeed.get", params={"filters": "post", "count": count})

    async def add_like(self, item_type: str, owner_id: int, item_id: int) -> Optional[Dict[str, Any]]:
        return await self._make_request("likes.add", params={"type": item_type, "owner_id": owner_id, "item_id": item_id})
    
    async def delete_friend(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self._make_request("friends.delete", params={"user_id": user_id})

    async def send_message(self, user_id: int, message: str) -> Optional[int]:
        return await self._make_request("messages.send", params={"user_id": user_id, "message": message, "random_id": random.randint(0, 2**31)})

    async def get_conversations(self, count: int = 200) -> Optional[Dict[str, Any]]:
        return await self._make_request("messages.getConversations", params={"count": count})

    async def get_photos(self, owner_id: int, count: int = 200) -> Optional[Dict[str, Any]]:
        return await self._make_request("photos.getAll", params={"owner_id": owner_id, "count": count, "extended": 1})

    async def set_online(self) -> Optional[int]:
        return await self._make_request("account.setOnline")

async def is_token_valid(vk_token: str) -> Optional[int]:
    vk_api = VKAPI(access_token=vk_token)
    try:
        user_info = await vk_api.get_user_info()
        return user_info.get('id') if user_info else None
    except VKAPIError:
        return None
    
async def get_groups(self, user_id: int, extended: int = 1, fields: str = "members_count", count: int = 1000) -> Optional[Dict[str, Any]]:
        return await self._make_request("groups.get", params={"user_id": user_id, "extended": extended, "fields": fields, "count": count})

async def leave_group(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.leave", params={"group_id": group_id})

# --- backend/app\services\websocket_manager.py ---

# backend/app/services/websocket_manager.py
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from typing import Dict, Set
import structlog

log = structlog.get_logger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: int, message: str):
        if user_id in self.active_connections:
            websockets = self.active_connections[user_id]
            for websocket in websockets:
                await websocket.send_text(message)

manager = WebSocketManager()

async def redis_listener(redis_client: Redis):
    async with redis_client.pubsub() as pubsub:
        await pubsub.psubscribe("ws:user:*")
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    channel = message['channel']
                    user_id = int(channel.split(':')[-1])
                    data = message['data']
                    await manager.broadcast_to_user(user_id, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("redis_listener.error", error=str(e))

# --- backend/app\services\__init__.py ---



# --- backend/app\tasks\base_task.py ---

import asyncio
from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import engine
from app.db.models import TaskHistory
from app.core.config import settings
from app.tasks.utils import run_async_from_sync

AsyncSessionFactory_Celery = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(settings.database_url.replace("+asyncpg", ""))
SyncSessionFactory_Celery = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


class AppBaseTask(Task):
    acks_late = True

    # --- ИЗМЕНЕНИЕ: Добавлена обертка для асинхронных вызовов ---
    def _run_async_from_sync(self, coro):
        return run_async_from_sync(coro)

    def _update_task_history_sync(self, task_history_id: int, status: str, result: str):
        if not task_history_id:
            return
        
        session = SyncSessionFactory_Celery()
        try:
            task_history = session.get(TaskHistory, task_history_id)
            if task_history:
                task_history.status = status
                task_history.result = result
                session.commit()
        except Exception as e:
            print(f"CRITICAL: Failed to update task history {task_history_id}: {e}")
            session.rollback()
        finally:
            session.close()


    def on_failure(self, exc, task_id, args, kwargs, einfo):
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        error_message = f"Задача провалена: {exc!r}"
        self._update_task_history_sync(task_history_id, "FAILURE", error_message)

    def on_success(self, retval, task_id, args, kwargs):
        task_history_id = kwargs.get('task_history_id') or (args[0] if args else None)
        success_message = "Задача успешно выполнена."
        self._update_task_history_sync(task_history_id, "SUCCESS", success_message)

# --- backend/app\tasks\cron.py ---

# backend/app/tasks/cron.py
import asyncio
import datetime
import structlog
from redis.asyncio import Redis
from sqlalchemy import func, select, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, Automation, TaskHistory, User, Notification
)
from app.tasks.runner import (
    like_feed, add_recommended_friends, accept_friend_requests, 
    remove_friends_by_criteria, view_stories, like_friends_feed, eternal_online,
    birthday_congratulation
)
from app.core.config_loader import PLAN_CONFIG
from app.core.plans import get_limits_for_plan
from app.tasks.utils import run_async_from_sync
import pytz

log = structlog.get_logger(__name__)

TASK_FUNC_MAP = {
    "like_feed": like_feed,
    "add_recommended": add_recommended_friends,
    "birthday_congratulation": birthday_congratulation,
    "accept_friends": accept_friend_requests,
    "remove_friends": remove_friends_by_criteria,
    "view_stories": view_stories,
    "like_friends_feed": like_friends_feed,
    "eternal_online": eternal_online,
}

async def _create_and_run_task(session, user_id, task_name, settings):
    task_func = TASK_FUNC_MAP.get(task_name)
    if not task_func:
        log.warn("cron.task_not_found", task_name=task_name)
        return

    task_kwargs = settings.copy() if settings else {}
    if 'task_history_id' in task_kwargs:
        del task_kwargs['task_history_id']

    task_history = TaskHistory(user_id=user_id, task_name=task_name, status="PENDING", parameters=task_kwargs)
    session.add(task_history)
    await session.flush()

    queue_name = 'low_priority' if task_name in ['eternal_online'] else 'default'

    task_result = task_func.apply_async(
        kwargs={'task_history_id': task_history.id, **task_kwargs},
        queue=queue_name
    )
    task_history.celery_task_id = task_result.id

async def _aggregate_daily_stats_async():
    async with AsyncSessionFactory() as session:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        week_id = yesterday.strftime('%Y-%W')
        month_id = yesterday.strftime('%Y-%m')

        stmt = select(
            DailyStats.user_id,
            func.sum(DailyStats.likes_count).label("likes"),
            func.sum(DailyStats.friends_added_count).label("friends_added"),
            func.sum(DailyStats.friend_requests_accepted_count).label("req_accepted")
        ).where(DailyStats.date == yesterday).group_by(DailyStats.user_id)
        
        result = await session.execute(stmt)
        daily_sums = result.all()

        if not daily_sums:
            log.info("aggregate_daily_stats.no_data", date=yesterday.isoformat())
            return

        weekly_values = [{"user_id": r.user_id, "week_identifier": week_id, "likes_count": r.likes, "friends_added_count": r.friends_added, "friend_requests_accepted_count": r.req_accepted} for r in daily_sums]
        insert_stmt_w = insert(WeeklyStats).values(weekly_values)
        update_stmt_w = insert_stmt_w.on_conflict_do_update(
            index_elements=['user_id', 'week_identifier'],
            set_={'likes_count': WeeklyStats.likes_count + insert_stmt_w.excluded.likes_count, 'friends_added_count': WeeklyStats.friends_added_count + insert_stmt_w.excluded.friends_added_count, 'friend_requests_accepted_count': WeeklyStats.friend_requests_accepted_count + insert_stmt_w.excluded.friend_requests_accepted_count}
        )
        await session.execute(update_stmt_w)

        monthly_values = [{"user_id": r.user_id, "month_identifier": month_id, "likes_count": r.likes, "friends_added_count": r.friends_added, "friend_requests_accepted_count": r.req_accepted} for r in daily_sums]
        insert_stmt_m = insert(MonthlyStats).values(monthly_values)
        update_stmt_m = insert_stmt_m.on_conflict_do_update(
            index_elements=['user_id', 'month_identifier'],
            set_={'likes_count': MonthlyStats.likes_count + insert_stmt_m.excluded.likes_count, 'friends_added_count': MonthlyStats.friends_added_count + insert_stmt_m.excluded.friends_added_count, 'friend_requests_accepted_count': MonthlyStats.friend_requests_accepted_count + insert_stmt_m.excluded.friend_requests_accepted_count}
        )
        await session.execute(update_stmt_m)

        await session.commit()
        log.info("aggregate_daily_stats.success", users_count=len(daily_sums), date=yesterday.isoformat())

async def _run_daily_automations_async(automation_group: str):
    """
    Основная логика для запуска периодических автоматизаций.
    Безопасно для многопроцессной среды Celery.
    """
    redis_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=2, decode_responses=True)
    lock_key = f"lock:task:run_automations:{automation_group}"
    
    # Пытаемся установить блокировку на 4 минуты. Если не удалось - значит, задача уже выполняется.
    if not await redis_client.set(lock_key, "1", ex=240, nx=True):
        log.warn("run_daily_automations.already_running", group=automation_group)
        await redis_client.close()
        return
    
    try:
        async with AsyncSessionFactory() as session:
            now_utc = datetime.datetime.utcnow()
            # Устанавливаем часовой пояс Москвы для проверки кастомного расписания
            moscow_tz = pytz.timezone("Europe/Moscow")
            now_moscow = now_utc.astimezone(moscow_tz)

            automation_ids_in_group = []
            if automation_group == 'standard':
                automation_ids_in_group = ["like_feed", "add_recommended", "accept_friends", "remove_friends", "like_friends_feed", "view_stories", "birthday_congratulation"]
            elif automation_group == 'online':
                automation_ids_in_group = ["eternal_online"]

            if not automation_ids_in_group:
                log.warn("run_daily_automations.unknown_group", group=automation_group)
                return

            available_plans = [
                plan_name for plan_name, config in PLAN_CONFIG.items()
                if config.get("available_features") == "*" or any(auto_id in config.get("available_features", []) for auto_id in automation_ids_in_group)
            ]

            stmt = (
                select(Automation)
                .join(User)
                .where(
                    Automation.is_active == True,
                    Automation.automation_type.in_(automation_ids_in_group),
                    User.plan.in_(available_plans),
                    or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
                )
                .options(selectinload(Automation.user))
            )

            result = await session.execute(stmt)
            active_automations = result.scalars().unique().all()

            if not active_automations:
                return

            log.info("run_daily_automations.start", count=len(active_automations), group=automation_group)
            
            for automation in active_automations:
                # Специальная логика для "Вечного онлайна" с кастомным расписанием
                if automation.automation_type == "eternal_online":
                    settings = automation.settings or {}
                    if settings.get("schedule_type") == "custom":
                        days_of_week = settings.get("days_of_week", [])
                        start_time_str = settings.get("start_time")
                        end_time_str = settings.get("end_time")
                        
                        # Проверяем день недели (0=Понедельник, ..., 6=Воскресенье в Python)
                        if now_moscow.weekday() not in days_of_week:
                            continue # Пропускаем, если сегодня не рабочий день
                        
                        # Проверяем время
                        if start_time_str and end_time_str:
                            try:
                                start_time = datetime.datetime.strptime(start_time_str, "%H:%M").time()
                                end_time = datetime.datetime.strptime(end_time_str, "%H:%M").time()
                                
                                # Корректная обработка интервала через полночь (например, 22:00 - 02:00)
                                if start_time <= end_time:
                                    if not (start_time <= now_moscow.time() <= end_time):
                                        continue # Пропускаем, если не попадаем в интервал
                                else: # Интервал проходит через полночь
                                    if not (now_moscow.time() >= start_time or now_moscow.time() <= end_time):
                                        continue
                            except ValueError:
                                log.warn("run_daily_automations.invalid_time_format", user_id=automation.user_id)
                                continue # Пропускаем при неверном формате времени
                
                automation.last_run_at = now_utc
                await _create_and_run_task(session, user_id=automation.user_id, task_name=automation.automation_type, settings=automation.settings)
            
            await session.commit()
    finally:
        # Гарантированно освобождаем блокировку и закрываем соединение
        await redis_client.delete(lock_key)
        await redis_client.close()

async def _check_expired_plans_async():
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        # <-- ИЗМЕНЕНИЕ: Упрощенная и более эффективная логика для поиска истекших планов
        stmt = select(User).where(
            User.plan != 'Expired',
            User.plan_expires_at != None,
            User.plan_expires_at < now
        )
        result = await session.execute(stmt)
        expired_users = result.scalars().all()

        if not expired_users:
            return

        log.info("plans.expired_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan("Expired")
        user_ids_to_deactivate = [user.id for user in expired_users]

        notifications_to_add = [
            Notification(user_id=user.id, message=f"Срок действия тарифа '{user.plan}' истек. Все автоматизации остановлены.", level="error")
            for user in expired_users
        ]
        session.add_all(notifications_to_add)

        deactivate_automations_stmt = update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False)
        await session.execute(deactivate_automations_stmt)

        deactivate_users_stmt = update(User).where(User.id.in_(user_ids_to_deactivate)).values(
            plan="Expired",
            daily_likes_limit=expired_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=expired_plan_limits["daily_add_friends_limit"]
        )
        await session.execute(deactivate_users_stmt)
        
        await session.commit()
        log.info("plans.expired_processed_and_deactivated", count=len(user_ids_to_deactivate))


@celery_app.task(name="app.tasks.cron.aggregate_daily_stats")
def aggregate_daily_stats():
    run_async_from_sync(_aggregate_daily_stats_async())

@celery_app.task(name="app.tasks.cron.run_daily_automations", ignore_result=True)
def run_daily_automations(automation_group: str):
    run_async_from_sync(_run_daily_automations_async(automation_group))

@celery_app.task(name="app.tasks.cron.check_expired_plans")
def check_expired_plans():
    run_async_from_sync(_check_expired_plans_async())

# --- backend/app\tasks\maintenance.py ---

# backend/app/tasks/maintenance.py
import datetime
import structlog
from sqlalchemy import delete

from app.celery_app import celery_app
from celery import Task

from app.db.session import AsyncSessionFactory
from app.db.models import TaskHistory, User
from app.tasks.utils import run_async_from_sync

log = structlog.get_logger(__name__)

async def _clear_old_task_history_async():
    async with AsyncSessionFactory() as session:
        # Удаляем записи старше 90 дней для PRO и Plus
        pro_plus_cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=90)
        stmt_pro = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                session.query(User.id).filter(User.plan.in_(['PRO', 'Plus']))
            ),
            TaskHistory.created_at < pro_plus_cutoff
        )
        pro_result = await session.execute(stmt_pro)

        # Удаляем записи старше 30 дней для Базового и Истекшего
        base_cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        stmt_base = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                session.query(User.id).filter(User.plan.in_(['Базовый', 'Expired']))
            ),
            TaskHistory.created_at < base_cutoff
        )
        base_result = await session.execute(stmt_base)

        await session.commit()
        total_deleted = pro_result.rowcount + base_result.rowcount
        log.info("maintenance.task_history_cleaned", count=total_deleted)

@celery_app.task(name="app.tasks.maintenance.clear_old_task_history")
def clear_old_task_history():
    run_async_from_sync(_clear_old_task_history_async())

# --- backend/app\tasks\profile_parser.py ---

# backend/app/tasks/profile_parser.py
import asyncio
import datetime
import structlog
from sqlalchemy import select, or_

from app.celery_app import celery_app
from celery import Task

from app.db.session import AsyncSessionFactory
from app.db.models import User 
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.services.vk_api import VKAuthError
from app.tasks.utils import run_async_from_sync

log = structlog.get_logger(__name__)

async def _snapshot_all_users_metrics_async():
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        stmt = select(User).where(or_(User.plan_expires_at == None, User.plan_expires_at > now))
        result = await session.execute(stmt)
        active_users = result.scalars().all()

        if not active_users:
            log.info("snapshot_metrics_task.no_active_users")
            return

        log.info("snapshot_metrics_task.start", count=len(active_users))
        
        tasks = [_process_user(user) for user in active_users]
        await asyncio.gather(*tasks)
        
        log.info("snapshot_metrics_task.finished")

async def _process_user(user: User):
    async with AsyncSessionFactory() as user_session:
        try:
            service = ProfileAnalyticsService(db=user_session, user=user, emitter=None)
            await service.snapshot_profile_metrics()
        except VKAuthError:
            log.warn("snapshot_metrics_task.auth_error", user_id=user.id)
        except Exception as e:
            log.error("snapshot_metrics_task.user_error", user_id=user.id, error=str(e))

@celery_app.task(name="app.tasks.profile_parser.snapshot_all_users_metrics")
def snapshot_all_users_metrics():
    run_async_from_sync(_snapshot_all_users_metrics_async())

# --- backend/app\tasks\runner.py ---

from app.celery_app import celery_app
from celery import Task
from redis.asyncio import Redis as AsyncRedis
import asyncio
from sqlalchemy.future import select
import random
from sqlalchemy.orm import selectinload
from app.db.models import Scenario, User, TaskHistory
from app.services.event_emitter import RedisEventEmitter
from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService
from app.core.config import settings
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAuthError, VKRateLimitError, VKAPIError
from app.tasks.base_task import AppBaseTask, AsyncSessionFactory_Celery
import structlog
# --- ИЗМЕНЕНИЕ: Исправлен неверный путь импорта ---
from app.tasks.utils import run_async_from_sync
from app.services.humanizer import Humanizer

log = structlog.get_logger(__name__)

TASK_SERVICE_MAP = {
    "like_feed": (FeedService, "like_newsfeed"),
    "like_friends_feed": (FeedService, "like_friends_feed"),
    "add_recommended": (OutgoingRequestService, "add_recommended_friends"),
    "accept_friends": (IncomingRequestService, "accept_friend_requests"),
    "remove_friends": (FriendManagementService, "remove_friends_by_criteria"),
    "view_stories": (StoryService, "view_stories"),
    "birthday_congratulation": (AutomationService, "congratulate_friends_with_birthday"),
    "mass_messaging": (MessageService, "send_mass_message"),
    "eternal_online": (AutomationService, "set_online_status"),
    "leave_groups": (GroupManagementService, "leave_groups_by_criteria"),
}

async def _execute_task_logic(task_history_id: int, task_name_key: str, **kwargs):
    redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)
    emitter = RedisEventEmitter(redis_client)
    
    try:
        async with AsyncSessionFactory_Celery() as session:
            task_history = await session.get(TaskHistory, task_history_id)
            if not task_history:
                log.error("task_runner.history_not_found", id=task_history_id)
                return

            user = await session.get(User, task_history.user_id)
            if not user:
                raise RuntimeError(f"User {task_history.user_id} not found")
                
            emitter.set_context(user.id, task_history.id)
            task_history.status = "STARTED"
            await session.commit()
            await emitter.send_task_status_update(status="STARTED", task_name=task_history.task_name, created_at=task_history.created_at)

            try:
                ServiceClass, method_name = TASK_SERVICE_MAP[task_name_key]
                service_instance = ServiceClass(db=session, user=user, emitter=emitter)
                await getattr(service_instance, method_name)(**kwargs)

            except (VKRateLimitError, VKAPIError) as e:
                await emitter.send_task_status_update(status="RETRY", result=f"Ошибка VK API: {e.message}", task_name=task_history.task_name, created_at=task_history.created_at)
                raise e
            
            except (VKAuthError, UserActionException) as e:
                await emitter.send_system_notification(session, str(e), "error")
                raise e
            
            except Exception as e:
                log.exception("task_runner.unhandled_exception", id=task_history_id, error=str(e))
                await emitter.send_system_notification(session, f"Произошла внутренняя ошибка: {e}", "error")
                raise
    finally:
        await redis_client.close()

# --- ИЗМЕНЕНИЕ: Добавлена новая задача ---
def _create_task(name, **kwargs):
    @celery_app.task(name=f"app.tasks.runner.{name}", bind=True, base=AppBaseTask, **kwargs)
    def task_wrapper(self: Task, task_history_id: int, **task_kwargs):
        return run_async_from_sync(_execute_task_logic(task_history_id, name, **task_kwargs))
    return task_wrapper

like_feed = _create_task("like_feed", max_retries=3, default_retry_delay=300)
add_recommended_friends = _create_task("add_recommended", max_retries=3, default_retry_delay=300)
accept_friend_requests = _create_task("accept_friends", max_retries=3, default_retry_delay=60)
remove_friends_by_criteria = _create_task("remove_friends", max_retries=2, default_retry_delay=60)
view_stories = _create_task("view_stories", max_retries=2, default_retry_delay=60)
birthday_congratulation = _create_task("birthday_congratulation", max_retries=2, default_retry_delay=120)
mass_messaging = _create_task("mass_messaging", max_retries=2, default_retry_delay=300)
eternal_online = _create_task("eternal_online", max_retries=5, default_retry_delay=60)
like_friends_feed = _create_task("like_friends_feed", max_retries=3, default_retry_delay=300)
leave_groups_by_criteria = _create_task("leave_groups", max_retries=2, default_retry_delay=60)


@celery_app.task(bind=True, base=AppBaseTask, name="app.tasks.runner.run_scenario_from_scheduler")
def run_scenario_from_scheduler(self: Task, scenario_id: int, user_id: int):
    async def _run_scenario_logic():
        redis_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
        lock_key = f"lock:scenario:user:{user_id}"
        
        if not await redis_client.set(lock_key, "1", ex=3600, nx=True):
            log.warn("scenario.runner.already_running", scenario_id=scenario_id, user_id=user_id)
            await redis_client.close()
            return

        log.info("scenario.runner.start", scenario_id=scenario_id)
        try:
            async with AsyncSessionFactory_Celery() as session:
                stmt = select(Scenario).where(Scenario.id == scenario_id).options(selectinload(Scenario.steps), selectinload(Scenario.user))
                scenario = (await session.execute(stmt)).scalar_one_or_none()
                
                if not scenario or not scenario.is_active:
                    log.warn("scenario.runner.not_found_or_inactive", scenario_id=scenario_id)
                    return

                emitter = RedisEventEmitter(redis_client)
                emitter.set_context(user_id=user_id)
                humanizer = Humanizer(delay_profile=scenario.user.delay_profile, logger_func=emitter.send_log)

                sorted_steps = sorted(scenario.steps, key=lambda s: s.step_order)

                for step in sorted_steps:
                    ServiceClass, method_name = TASK_SERVICE_MAP[step.action_type]
                    service_instance = ServiceClass(db=session, user=scenario.user, emitter=emitter)
                    
                    batch_settings = step.batch_settings or {}
                    parts = batch_settings.get("parts", 1)
                    total_count = step.settings.get("count", 0)

                    if parts > 1 and total_count > 0:
                        count_per_part = total_count // parts
                        for i in range(parts):
                            current_kwargs = step.settings.copy()
                            current_kwargs['count'] = count_per_part
                            if i == parts - 1:
                                current_kwargs['count'] += total_count % parts

                            log.info("scenario.step.batch_execution", scenario_id=scenario_id, step=step.action_type, batch=f"{i+1}/{parts}")
                            await getattr(service_instance, method_name)(**current_kwargs)
                            
                            if i < parts - 1:
                                await humanizer._sleep(60, 180, f"Пауза между частями шага ({i+1}/{parts})")
                    else:
                        await getattr(service_instance, method_name)(**step.settings)
        except Exception as e:
            log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e))
        finally:
            await redis_client.delete(lock_key)
            await redis_client.close()
            log.info("scenario.runner.finished", scenario_id=scenario_id)
    
    return run_async_from_sync(_run_scenario_logic())

# --- backend/app\tasks\utils.py ---

# backend/app/tasks/utils.py
import asyncio

def run_async_from_sync(coro):
    """
    Надежно запускает асинхронную корутину из синхронной задачи Celery,
    используя стандартный asyncio.run().
    """
    return asyncio.run(coro)

# --- backend/app\tasks\__init__.py ---


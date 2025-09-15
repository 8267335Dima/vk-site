

# --- backend/app\admin.py ---

# backend/app/admin.py
import secrets
from datetime import timedelta
from fastapi import Request, HTTPException, status
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from jose import jwt, JWTError

# УЛУЧШЕНИЕ: Импортируем модели из нового структурированного пакета
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

# --- backend/app\arq_config.py ---

# backend/app/arq_config.py
from arq.connections import RedisSettings

# Единый источник настроек Redis для ARQ.
# Используем базу данных Redis №4, чтобы не пересекаться с кэшем или limiter'ом.
redis_settings = RedisSettings.from_dsn("redis://localhost:6379/4")

# --- backend/app\main.py ---

# backend/app/main.py
import asyncio
import structlog
from fastapi import APIRouter, FastAPI, Request, status, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from redis.asyncio import Redis
from redis.exceptions import RedisError
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from prometheus_fastapi_instrumentator import Instrumentator

# --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
# from app.celery_app import celery_app # <-- УДАЛЕНО: Celery больше не используется
from app.arq_config import redis_settings # <-- ИЗМЕНЕНО: Импорт из нового центрального конфига
from arq.connections import create_pool
# -------------------------

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.admin import init_admin
from app.api.endpoints import (
    auth_router, users_router, websockets_router,
    stats_router, automations_router, billing_router,
    analytics_router, scenarios_router, notifications_router, proxies_router,
    tasks_router, posts_router, teams_router
)
from app.services.websocket_manager import redis_listener
from fastapi.routing import APIRoute

configure_logging()
log = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управляет жизненным циклом приложения, включая запуск и остановку ресурсов,
    а также выполняет диагностику при старте.
    """
    # --- СТАРТ ПРИЛОЖЕНИЯ ---
    limiter_redis = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0", encoding="utf-8", decode_responses=True)
    cache_redis = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/3", encoding="utf-8")
    pubsub_redis = Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", decode_responses=True)
    redis_task = None

    try:
        await FastAPILimiter.init(limiter_redis)
        FastAPICache.init(RedisBackend(cache_redis), prefix="fastapi-cache")
        redis_task = asyncio.create_task(redis_listener(pubsub_redis))
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        # Создаем пул соединений ARQ и сохраняем его в состоянии приложения
        app.state.arq_pool = await create_pool(redis_settings)
        # -------------------------
        log.info("lifespan.startup", message="Dependencies initialized.")
    except RedisError as e:
        log.error("lifespan.startup.error", error=str(e), message="Could not connect to Redis.")

    # --- ДИАГНОСТИКА (без изменений) ---
    print("\n--- FastAPI ROUTE DEPENDENCY DIAGNOSTICS ---")
    for route in app.routes:
        if isinstance(route, APIRoute):
            if route.path == "/api/v1/scenarios" and "POST" in route.methods:
                print(f"Found route: {route.methods} {route.path}")
                print(f"Endpoint function: {route.endpoint.__name__}")
                for dep in route.dependant.dependencies:
                    if hasattr(dep.call, "__name__"):
                         print(f"--> Depends on function: '{dep.call.__name__}'")
                    else:
                         print(f"--> Depends on object: {dep.call}")
    print("--- END DIAGNOSTICS ---\n")

    yield

    # --- ОСТАНОВКА ПРИЛОЖЕНИЯ ---
    if redis_task:
        redis_task.cancel()
        try:
            await redis_task
        except asyncio.CancelledError:
            log.info("lifespan.shutdown", message="Redis listener task cancelled.")

    await app.state.arq_pool.close()

    # --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
    await limiter_redis.aclose()
    await cache_redis.aclose()
    await pubsub_redis.aclose()

    await FastAPILimiter.close() # Этот метод из библиотеки, его не трогаем
    FastAPICache.reset()

    await engine.dispose()

    log.info("lifespan.shutdown", message="All resources cleaned up completely.")


app = FastAPI(title="Zenith API", version="4.0.0", docs_url="/api/docs", redoc_url="/api/redoc", lifespan=lifespan)

instrumentator = Instrumentator().instrument(app)
instrumentator.expose(app, endpoint="/api/metrics")

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

init_admin(app, engine)

if settings.ALLOWED_ORIGINS:
    allowed_origins_list = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(',')]
else:
    allowed_origins_list = ["http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Tags:
    AUTH = "Аутентификация"
    USERS = "Пользователи и Профили"
    PROXIES = "Прокси"
    TASKS = "Задачи и История"
    STATS = "Статистика"
    AUTOMATIONS = "Автоматизации"
    BILLING = "Тарифы и оплата"
    ANALYTICS = "Аналитика"
    SCENARIOS = "Сценарии"
    NOTIFICATIONS = "Уведомления"
    POSTS = "Планировщик постов"
    TEAMS = "Командный функционал"
    WEBSOCKETS = "WebSockets"
    SYSTEM = "Система"

api_router_v1 = APIRouter()
api_router_v1.include_router(auth_router, prefix="/auth", tags=[Tags.AUTH])
api_router_v1.include_router(users_router, prefix="/users", tags=[Tags.USERS])
api_router_v1.include_router(proxies_router, prefix="/proxies", tags=[Tags.PROXIES])
api_router_v1.include_router(tasks_router, prefix="/tasks", tags=[Tags.TASKS])
api_router_v1.include_router(stats_router, prefix="/stats", tags=[Tags.STATS])
api_router_v1.include_router(automations_router, prefix="/automations", tags=[Tags.AUTOMATIONS])
api_router_v1.include_router(billing_router, prefix="/billing", tags=[Tags.BILLING])
api_router_v1.include_router(analytics_router, prefix="/analytics", tags=[Tags.ANALYTICS])
api_router_v1.include_router(scenarios_router, prefix="/scenarios", tags=[Tags.SCENARIOS])
api_router_v1.include_router(notifications_router, prefix="/notifications", tags=[Tags.NOTIFICATIONS])
api_router_v1.include_router(posts_router, prefix="/posts", tags=[Tags.POSTS])
api_router_v1.include_router(teams_router, prefix="/teams", tags=[Tags.TEAMS])
api_router_v1.include_router(websockets_router, prefix="", tags=[Tags.WEBSOCKETS])

app.include_router(api_router_v1, prefix="/api/v1")

@app.get("/api/health", status_code=status.HTTP_200_OK, tags=[Tags.SYSTEM])
async def health_check():
    return {"status": "ok"}

# --- backend/app\worker.py ---

# backend/app/worker.py
import asyncio
from arq import cron
from arq.connections import create_pool

# Импортируем настройки из нового центрального файла
from app.arq_config import redis_settings

# Импортируем асинхронные функции, которые будут нашими задачами
from app.tasks.cron_jobs import (
    aggregate_daily_stats_job,
    check_expired_plans_job,
    generate_all_heatmaps_job,
    update_friend_request_statuses_job,
    run_standard_automations_job,
    run_online_automations_job,
)
from app.tasks.maintenance_jobs import clear_old_task_history_job
from app.tasks.profile_parser_jobs import snapshot_all_users_metrics_job
from app.tasks.main_tasks import (
    like_feed_task,
    add_recommended_friends_task,
    accept_friend_requests_task,
    remove_friends_by_criteria_task,
    view_stories_task,
    birthday_congratulation_task,
    mass_messaging_task,
    eternal_online_task,
    leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
    publish_scheduled_post_task,
    run_scenario_from_scheduler_task,
)

functions = [
    like_feed_task,
    add_recommended_friends_task,
    accept_friend_requests_task,
    remove_friends_by_criteria_task,
    view_stories_task,
    birthday_congratulation_task,
    mass_messaging_task,
    eternal_online_task,
    leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
    publish_scheduled_post_task,
    run_scenario_from_scheduler_task,
]

# --- ИЗМЕНЕНИЯ ЗДЕСЬ: Исправлен синтаксис для ARQ cron ---
cron_jobs = [
    cron(aggregate_daily_stats_job, hour=2, minute=5),
    cron(snapshot_all_users_metrics_job, hour=3),
    cron(clear_old_task_history_job, hour=4),
    # "Каждые 4 часа" -> {0, 4, 8, 12, 16, 20}
    cron(update_friend_request_statuses_job, hour={0, 4, 8, 12, 16, 20}, minute=0),
    cron(generate_all_heatmaps_job, hour=5),
    # "Каждые 15 минут" -> {0, 15, 30, 45}
    cron(check_expired_plans_job, minute={0, 15, 30, 45}),
    # "Каждые 5 минут" -> {0, 5, 10, ...}
    cron(run_standard_automations_job, minute=set(range(0, 60, 5))),
    # "Каждые 10 минут" -> {0, 10, 20, ...}
    cron(run_online_automations_job, minute={0, 10, 20, 30, 40, 50}),
]
# ----------------------------------------------------

async def startup(ctx):
    print("Воркер ARQ запущен и готов к работе.")
    ctx['redis_pool'] = await create_pool(redis_settings)

async def shutdown(ctx):
    if 'redis_pool' in ctx:
        await ctx['redis_pool'].close()
    print("Воркер ARQ остановлен.")

class WorkerSettings:
    functions = functions
    cron_jobs = cron_jobs
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown

# --- backend/app\__init__.py ---



# --- backend/app\api\dependencies.py ---

# backend/app/api/dependencies.py
from typing import Annotated, Dict, Any
from fastapi import Depends, HTTPException, Request, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, aliased
from arq.connections import ArqRedis

from app.core.config import settings
from app.db.models import User, ManagedProfile, TeamMember, TeamProfileAccess
from app.db.session import get_db, AsyncSessionFactory
from app.repositories.user import UserRepository
from fastapi_limiter.depends import RateLimiter

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/vk")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Не удалось проверить учетные данные",
    headers={"WWW-Authenticate": "Bearer"},
)

async def get_request_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.client.host if request.client else "unknown"

limiter = RateLimiter(times=5, minutes=1, identifier=get_request_identifier)

async def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool

async def get_token_payload(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except (JWTError, ValidationError):
        raise credentials_exception

async def _get_payload_from_string(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except (JWTError, ValidationError):
        raise credentials_exception

async def get_current_manager_user(
    payload: Dict[str, Any] = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db)
) -> User:
    user_repo = UserRepository(db)
    manager_id_str: str | None = payload.get("sub")
    if manager_id_str is None:
        raise credentials_exception
    
    manager = await user_repo.get(User, int(manager_id_str))
    if manager is None:
        raise credentials_exception
    return manager

async def get_current_active_profile(
    payload: Dict[str, Any] = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db)
) -> User:
    logged_in_user_id = int(payload.get("sub"))
    active_profile_id = int(payload.get("profile_id") or logged_in_user_id)
    
    tm_alias = aliased(TeamMember)
    stmt = (
        select(User)
        .outerjoin(ManagedProfile, and_(
            ManagedProfile.manager_user_id == logged_in_user_id,
            ManagedProfile.profile_user_id == User.id
        ))
        .outerjoin(tm_alias, tm_alias.user_id == logged_in_user_id)
        .outerjoin(TeamProfileAccess, and_(
            TeamProfileAccess.team_member_id == tm_alias.id,
            TeamProfileAccess.profile_user_id == User.id
        ))
        .where(
            User.id == active_profile_id,
            (User.id == logged_in_user_id) |
            (ManagedProfile.id != None) |
            (TeamProfileAccess.id != None)
        )
    )
    
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile:
        return profile
    
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к этому профилю запрещен.")


async def get_current_user_from_ws(token: str = Query(...)) -> User:
    async with AsyncSessionFactory() as session:
        payload = await _get_payload_from_string(token)
        profile_id = int(payload.get("profile_id") or payload.get("sub"))
        user = await session.get(User, profile_id)
        if not user:
            raise credentials_exception
        return user

# --- backend/app\api\__init__.py ---



# --- backend/app\api\endpoints\analytics.py ---

# --- backend/app/api/endpoints/analytics.py ---
import datetime
from collections import Counter
from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FriendsHistory, User, DailyStats, ProfileMetric, FriendRequestLog, FriendRequestStatus
from app.api.dependencies import get_current_active_profile
from app.db.session import get_db
from app.api.schemas.analytics import (
    AudienceAnalyticsResponse, AudienceStatItem, 
    SexDistributionResponse,
    ProfileGrowthResponse, ProfileGrowthItem,
    ProfileSummaryResponse, FriendRequestConversionResponse
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.db.models import PostActivityHeatmap
from app.api.schemas.analytics import PostActivityHeatmapResponse

router = APIRouter()


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
async def get_audience_analytics(current_user: User = Depends(get_current_active_profile)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)

    friends = await vk_api.get_user_friends(user_id=current_user.vk_id, fields="sex,bdate,city")
    if not friends:
        return AudienceAnalyticsResponse(city_distribution=[], age_distribution=[], sex_distribution=[])

    city_counter = Counter(
        friend['city']['title']
        for friend in friends
        if friend.get('city') and friend.get('city', {}).get('title') and not friend.get('deactivated')
    )
    top_cities = [
        AudienceStatItem(name=city, value=count)
        for city, count in city_counter.most_common(5)
    ]

    ages = [calculate_age(friend['bdate']) for friend in friends if friend.get('bdate') and not friend.get('deactivated')]
    age_groups = [get_age_group(age) for age in ages if age is not None]
    age_counter = Counter(age_groups)
    
    age_distribution = [
        AudienceStatItem(name=group, value=count)
        for group, count in sorted(age_counter.items())
    ]

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
@cache(expire=3600)
async def get_profile_summary(current_user: User = Depends(get_current_active_profile)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    
    user_info_list = await vk_api.get_user_info(user_ids=str(current_user.vk_id), fields="counters")
    user_info = user_info_list[0] if user_info_list else {}
    
    friends = user_info.get('counters', {}).get('friends', 0)
    followers = user_info.get('counters', {}).get('followers', 0)
    photos = user_info.get('counters', {}).get('photos', 0)
    
    wall_info = await vk_api.get_wall(owner_id=current_user.vk_id, count=0)
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
    current_user: User = Depends(get_current_active_profile),
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

@router.get("/friend-request-conversion", response_model=FriendRequestConversionResponse)
async def get_friend_request_conversion_stats(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(FriendRequestLog.status, func.count(FriendRequestLog.id))
        .where(FriendRequestLog.user_id == current_user.id)
        .group_by(FriendRequestLog.status)
    )
    result = await db.execute(stmt)
    stats = {status.name: count for status, count in result.all()}

    sent_total = stats.get('pending', 0) + stats.get('accepted', 0)
    accepted_total = stats.get('accepted', 0)
    
    conversion_rate = (accepted_total / sent_total * 100) if sent_total > 0 else 0

    return FriendRequestConversionResponse(
        sent_total=sent_total,
        accepted_total=accepted_total,
        conversion_rate=conversion_rate
    )

@router.get("/post-activity-heatmap", response_model=PostActivityHeatmapResponse)
async def get_post_activity_heatmap(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(PostActivityHeatmap).where(PostActivityHeatmap.user_id == current_user.id)
    result = await db.execute(stmt)
    heatmap_data = result.scalar_one_or_none()
    
    if not heatmap_data:
        return PostActivityHeatmapResponse(data=[[0]*24]*7) # Возвращаем пустую матрицу
        
    return PostActivityHeatmapResponse(data=heatmap_data.heatmap_data.get("data", [[0]*24]*7))

# --- backend/app\api\endpoints\auth.py ---

# backend/app/api/endpoints/auth.py

from datetime import timedelta, datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import User, LoginHistory
from app.api.schemas.auth import EnrichedTokenResponse
from app.services.vk_api import is_token_valid
from app.core.security import create_access_token, encrypt_data
from app.core.config import settings
from app.core.plans import get_limits_for_plan
from app.core.constants import PlanName
from app.api.dependencies import get_current_manager_user, limiter # Импортируем limiter

router = APIRouter()

class TokenRequest(BaseModel):
    vk_token: str


@router.post(
    "/vk",
    response_model=EnrichedTokenResponse,
    summary="Аутентификация или регистрация по токену VK",
    dependencies=[Depends(limiter)] # Оставляем защиту для production
)
async def login_via_vk(
    *,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token_request: TokenRequest
) -> EnrichedTokenResponse:
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
    
    base_plan_limits = get_limits_for_plan(PlanName.BASE)

    if user:
        user.encrypted_vk_token = encrypted_token
    else:
        user = User(
            vk_id=vk_id,
            encrypted_vk_token=encrypted_token,
            plan=PlanName.BASE,
            plan_expires_at=datetime.now(UTC) + timedelta(days=14),
            daily_likes_limit=base_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=base_plan_limits["daily_add_friends_limit"]
        )
        db.add(user)

    if str(vk_id) == settings.ADMIN_VK_ID:
        admin_limits = get_limits_for_plan(PlanName.PRO)
        user.is_admin = True
        user.plan = PlanName.PRO
        user.plan_expires_at = None
        user.daily_likes_limit = admin_limits["daily_likes_limit"]
        user.daily_add_friends_limit = admin_limits["daily_add_friends_limit"]

    await db.flush()
    await db.refresh(user)

    user_id = user.id

    login_entry = LoginHistory(
        user_id=user_id, # Используем сохраненный ID
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown")
    )
    db.add(login_entry)
    
    await db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Используем сохраненный ID для создания токена
    token_data = {"sub": str(user_id), "profile_id": str(user_id)}
    
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    return EnrichedTokenResponse(
        access_token=access_token,
        token_type="bearer",
        manager_id=user_id,
        active_profile_id=user_id
    )


class SwitchProfileRequest(BaseModel):
    profile_id: int

@router.post("/switch-profile", response_model=EnrichedTokenResponse, summary="Переключиться на другой управляемый профиль")
async def switch_profile(
    request_data: SwitchProfileRequest,
    manager: User = Depends(get_current_manager_user),
    db: AsyncSession = Depends(get_db)
) -> EnrichedTokenResponse:
    
    await db.refresh(manager, attribute_names=["managed_profiles"])
    
    allowed_profile_ids = {p.profile_user_id for p in manager.managed_profiles}
    allowed_profile_ids.add(manager.id)

    if request_data.profile_id not in allowed_profile_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к этому профилю запрещен.")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {
        "sub": str(manager.id),
        "profile_id": str(request_data.profile_id)
    }
    
    access_token = create_access_token(
        data=token_data, expires_delta=access_token_expires
    )

    return EnrichedTokenResponse(
        access_token=access_token, 
        token_type="bearer",
        manager_id=manager.id,
        active_profile_id=request_data.profile_id
    )

# --- backend/app\api\endpoints\automations.py ---

# backend/app/api/endpoints/automations.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import User, Automation
from app.api.dependencies import get_current_active_profile
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
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    query = select(Automation).where(Automation.user_id == current_user.id)
    result = await db.execute(query)
    user_automations_db = {auto.automation_type: auto for auto in result.scalars().all()}
    
    response_list = []
    for config_item in AUTOMATIONS_CONFIG:
        auto_type = config_item['id']
        db_item = user_automations_db.get(auto_type)
        
        is_available = is_feature_available_for_plan(current_user.plan, auto_type)
        
        response_list.append(AutomationStatus(
            automation_type=auto_type,
            is_active=db_item.is_active if db_item else False,
            settings=db_item.settings if db_item else config_item.get('default_settings', {}),
            name=config_item['name'],
            description=config_item['description'],
            is_available=is_available
        ))
        
    return response_list

@router.post("/{automation_type}", response_model=AutomationStatus)
async def update_automation(
    automation_type: str,
    request_data: AutomationUpdateRequest,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
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
            settings=request_data.settings or config_item.get('default_settings', {})
        )
        db.add(automation)
    else:
        automation.is_active = request_data.is_active
        if request_data.settings is not None:
            # Полностью заменяем настройки, а не обновляем.
            # Это позволяет фронтенду удалять ключи, отправляя объект без них.
            automation.settings = request_data.settings
    
    await db.commit()
    await db.refresh(automation)
    
    return AutomationStatus(
        automation_type=automation.automation_type,
        is_active=automation.is_active,
        settings=automation.settings,
        name=config_item['name'],
        description=config_item['description'],
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
from app.api.dependencies import get_current_active_profile
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
        if config.base_price is not None:
            available_plans.append({
                "id": plan_id,
                "display_name": config.display_name,
                "price": config.base_price, 
                "currency": "RUB", # Можно вынести в конфиг
                "description": config.description,
                "features": config.features,
                "is_popular": config.is_popular,
                "periods": [p.model_dump() for p in config.periods]
            })
    return {"plans": available_plans}


@router.post("/create-payment", response_model=CreatePaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    """
    Создает платеж, используя цены из централизованной конфигурации.
    """
    plan_id = request.plan_id
    months = request.months
    plan_info = PLAN_CONFIG.get(plan_id)

    if not plan_info or plan_info.base_price is None:
        raise HTTPException(status_code=400, detail="Неверное название тарифа или тариф не является платным.")

    base_price = plan_info.base_price
    final_price = base_price * months

    period_info = next((p for p in plan_info.periods if p.months == months), None)
    if period_info:
        final_price *= (1 - period_info.discount_percent / 100)
    
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
    ВНИМАНИЕ: В production-среде необходимо добавить проверку IP-адреса
    или подписи запроса от YooKassa для безопасности.
    """
    try:
        event = await request.json()
    except Exception:
        log.warn("webhook.invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    event_type = event.get("event")
    payment_data = event.get("object", {})
    payment_system_id = payment_data.get("id")
    
    log.info("webhook.received", event_type=event_type, payment_id=payment_system_id)
    
    if event_type == "payment.succeeded":
        if not payment_system_id:
            return {"status": "error", "message": "Payment ID missing."}

        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: УБИРАЕМ `async with db.begin():` ---
        # Сессия `db` уже находится в транзакции благодаря `Depends(get_db)`.
        # Все изменения будут автоматически закоммичены после успешного
        # завершения эндпоинта.

        query = select(Payment).where(Payment.payment_system_id == payment_system_id)
        payment = (await db.execute(query)).scalar_one_or_none()

        if not payment:
            log.warn("webhook.payment_not_found", payment_id=payment_system_id)
            return {"status": "ok"} # Возвращаем 200, чтобы система не повторяла запрос

        if payment.status == "succeeded":
            log.info("webhook.already_processed", payment_id=payment.id)
            return {"status": "ok"}
        
        user = await db.get(User, payment.user_id, with_for_update=True)
        if not user:
            log.error("webhook.user_not_found", user_id=payment.user_id)
            # Мы не можем ничего сделать, но должны вернуть 200, чтобы не было повторов
            payment.status = "failed"
            payment.error_message = "User not found"
            await db.commit()
            return {"status": "ok"}

        received_amount = float(payment_data.get("amount", {}).get("value", 0))
        if abs(received_amount - payment.amount) > 0.01:
            payment.status = "failed"
            payment.error_message = f"Amount mismatch: expected {payment.amount}, got {received_amount}"
            log.error("webhook.amount_mismatch", payment_id=payment.id, expected=payment.amount, got=received_amount)
            await db.commit()
            return {"status": "ok"}

        start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > datetime.datetime.now(datetime.UTC) else datetime.datetime.now(datetime.UTC)
        
        user.plan = payment.plan_name
        user.plan_expires_at = start_date + datetime.timedelta(days=30 * payment.months)
        
        new_limits = get_limits_for_plan(user.plan)
        user.daily_likes_limit = new_limits.get("daily_likes_limit", 0)
        user.daily_add_friends_limit = new_limits.get("daily_add_friends_limit", 0)

        payment.status = "succeeded"
        
        # FastAPI автоматически вызовет db.commit() после успешного выхода из этой функции
        log.info("webhook.success", user_id=user.id, plan=user.plan, expires_at=user.plan_expires_at)
        
    return {"status": "ok"}

# --- backend/app\api\endpoints\notifications.py ---

# backend/app/api/endpoints/notifications.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.db.session import get_db
from app.db.models import User, Notification
from app.api.dependencies import get_current_active_profile
from app.api.schemas.notifications import NotificationsResponse

router = APIRouter()

@router.get("", response_model=NotificationsResponse)
async def get_notifications(
    current_user: User = Depends(get_current_active_profile),
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
    current_user: User = Depends(get_current_active_profile),
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

# --- backend/app\api\endpoints\posts.py ---

# --- backend/app/api/endpoints/posts.py ---
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from arq.connections import ArqRedis

# --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
from app.db.session import get_db
from app.db.models import User, ScheduledPost
from app.api.dependencies import get_current_active_profile, get_arq_pool # Добавляем get_arq_pool
from app.api.schemas.posts import PostCreate, PostRead, PostUpdate, UploadedImageResponse
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
import structlog
# -------------------------

log = structlog.get_logger(__name__)
router = APIRouter()

@router.post("/upload-image", response_model=UploadedImageResponse)
async def upload_image_for_post(
    current_user: User = Depends(get_current_active_profile),
    image: UploadFile = File(...)
):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    try:
        image_bytes = await image.read()
        attachment_id = await vk_api.upload_photo_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except Exception as e:
        log.error("post.upload_image.failed", user_id=current_user.id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось загрузить изображение.")

@router.post("", response_model=PostRead)
async def schedule_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    arq_pool: ArqRedis = Depends(get_arq_pool)
    # -------------------------
):
    new_post = ScheduledPost(
        user_id=current_user.id,
        vk_profile_id=current_user.vk_id,
        **post_data.model_dump()
    )
    db.add(new_post)
    await db.flush() # Получаем ID для нового поста

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ: Используем ARQ вместо Celery ---
    job = await arq_pool.enqueue_job(
        'publish_scheduled_post_task', # Имя задачи, зарегистрированной в worker.py
        post_id=new_post.id,
        _defer_by=post_data.publish_at - datetime.utcnow() # Откладываем задачу
    )
    # ----------------------------------------------------

    new_post.celery_task_id = job.job_id # Используем старое поле для хранения ID задачи ARQ
    await db.commit()
    await db.refresh(new_post)
    return new_post

# ... (Здесь могут быть ваши эндпоинты GET, PUT, DELETE для управления постами) ...

# --- backend/app\api\endpoints\proxies.py ---

# backend/app/api/endpoints/proxies.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import datetime

from app.db.session import get_db
from app.db.models import User, Proxy
from app.api.dependencies import get_current_active_profile
from app.api.schemas.proxies import ProxyCreate, ProxyRead
from app.core.security import encrypt_data, decrypt_data
from app.services.proxy_service import ProxyService
# --- НОВЫЙ ИМПОРТ ---
from app.core.plans import is_feature_available_for_plan

router = APIRouter()

# --- НОВАЯ ЗАВИСИМОСТЬ ДЛЯ ПРОВЕРКИ ПРАВ ---
async def check_proxy_feature_access(current_user: User = Depends(get_current_active_profile)):
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

import json
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from croniter import croniter

from app.db.session import get_db
from app.db.models import User, Scenario, ScenarioStep, ScenarioStepType
from app.api.dependencies import get_current_active_profile
from app.api.schemas.scenarios import (
    Scenario as ScenarioSchema,
    ScenarioCreate,
    ScenarioUpdate,
    AvailableCondition,
    ScenarioStepNode,
    ScenarioEdge,
)

router = APIRouter()


# =====================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================

def _db_to_graph(scenario: Scenario) -> tuple[List[ScenarioStepNode], List[ScenarioEdge]]:
    """Конвертирует ORM-модели шагов и связей в формат для React Flow."""
    nodes: List[ScenarioStepNode] = []
    edges: List[ScenarioEdge] = []

    if not scenario.steps:
        return nodes, edges

    db_id_to_frontend_id = {
        step.id: str(step.details.get("id", step.id)) for step in scenario.steps
    }

    for step in scenario.steps:
        node_id_str = db_id_to_frontend_id[step.id]

        # Тип узла для фронта
        if step.step_type == ScenarioStepType.action and step.details.get("action_type") == "start":
            node_type = "start"
        else:
            node_type = step.step_type.value

        nodes.append(
            ScenarioStepNode(
                id=node_id_str,
                type=node_type,
                data=step.details.get("data", {}),
                position={"x": step.position_x, "y": step.position_y},
            )
        )

        source_id_str = db_id_to_frontend_id[step.id]

        if step.next_step_id and step.next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.next_step_id]
            edges.append(
                ScenarioEdge(
                    id=f"e{source_id_str}-{target_id_str}",
                    source=source_id_str,
                    target=target_id_str,
                )
            )

        if step.on_success_next_step_id and step.on_success_next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.on_success_next_step_id]
            edges.append(
                ScenarioEdge(
                    id=f"e{source_id_str}-{target_id_str}-success",
                    source=source_id_str,
                    target=target_id_str,
                    sourceHandle="on_success",
                )
            )

        if step.on_failure_next_step_id and step.on_failure_next_step_id in db_id_to_frontend_id:
            target_id_str = db_id_to_frontend_id[step.on_failure_next_step_id]
            edges.append(
                ScenarioEdge(
                    id=f"e{source_id_str}-{target_id_str}-failure",
                    source=source_id_str,
                    target=target_id_str,
                    sourceHandle="on_failure",
                )
            )

    return nodes, edges


def _build_steps_from_nodes(nodes: List[ScenarioStepNode]) -> Dict[str, ScenarioStep]:
    """Создаёт объекты шагов из узлов фронта (без связей)."""
    node_map: Dict[str, ScenarioStep] = {}
    for node in nodes:
        if node.type == "start":
            step_type = ScenarioStepType.action
            details = {"id": node.id, "data": node.data, "action_type": "start"}
        elif node.type == "action":
            step_type = ScenarioStepType.action
            details = {"id": node.id, "data": node.data}
        elif node.type == "condition":
            step_type = ScenarioStepType.condition
            details = {"id": node.id, "data": node.data}
        else:
            raise HTTPException(
                status_code=400, detail=f"Неизвестный тип узла: {node.type}"
            )

        step = ScenarioStep(
            step_type=step_type,
            details=details,
            position_x=node.position.get("x", 0),
            position_y=node.position.get("y", 0),
        )
        node_map[node.id] = step

    return node_map


def _apply_edges(node_map: Dict[str, ScenarioStep], edges: List[ScenarioEdge]) -> None:
    """Проставляет связи между шагами по рёбрам."""
    for edge in edges:
        source_step = node_map.get(edge.source)
        target_step = node_map.get(edge.target)
        if not source_step or not target_step:
            continue

        if source_step.step_type == ScenarioStepType.action:
            source_step.next_step_id = target_step.id
        elif source_step.step_type == ScenarioStepType.condition:
            if edge.sourceHandle == "on_success":
                source_step.on_success_next_step_id = target_step.id
            elif edge.sourceHandle == "on_failure":
                source_step.on_failure_next_step_id = target_step.id


def _find_start_step(node_map: Dict[str, ScenarioStep], nodes: List[ScenarioStepNode]) -> int | None:
    """Находит стартовый шаг (если есть)."""
    start_node = next((node for node in nodes if node.type == "start"), None)
    if start_node:
        return node_map[start_node.id].id
    return None


# =====================================================
# ЭНДПОИНТЫ
# =====================================================

@router.get("/available-conditions", response_model=List[AvailableCondition])
async def get_available_conditions():
    """Условные поля для сценариев (UI-справочник)."""
    return [
        {
            "key": "friends_count",
            "label": "Количество друзей",
            "type": "number",
            "operators": ["==", "!=", ">", "<", ">=", "<="],
        },
        {
            "key": "conversion_rate",
            "label": "Конверсия заявок (%)",
            "type": "number",
            "operators": [">", "<", ">=", "<="],
        },
        {
            "key": "day_of_week",
            "label": "День недели",
            "type": "select",
            "operators": ["==", "!="],
            "options": [
                {"value": "1", "label": "Понедельник"},
                {"value": "2", "label": "Вторник"},
                {"value": "3", "label": "Среда"},
                {"value": "4", "label": "Четверг"},
                {"value": "5", "label": "Пятница"},
                {"value": "6", "label": "Суббота"},
                {"value": "7", "label": "Воскресенье"},
            ],
        },
    ]


@router.get("", response_model=List[ScenarioSchema])
async def get_user_scenarios(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Scenario)
        .where(Scenario.user_id == current_user.id)
        .options(selectinload(Scenario.steps))
    )
    result = await db.execute(stmt)
    scenarios_db = result.scalars().unique().all()

    return [
        ScenarioSchema(
            id=s.id,
            name=s.name,
            schedule=s.schedule,
            is_active=s.is_active,
            nodes=_db_to_graph(s)[0],
            edges=_db_to_graph(s)[1],
        )
        for s in scenarios_db
    ]


@router.get("/{scenario_id}", response_model=ScenarioSchema)
async def get_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Scenario)
        .where(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
        .options(selectinload(Scenario.steps))
    )
    result = await db.execute(stmt)
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")

    nodes, edges = _db_to_graph(scenario)
    return ScenarioSchema(
        id=scenario.id,
        name=scenario.name,
        schedule=scenario.schedule,
        is_active=scenario.is_active,
        nodes=nodes,
        edges=edges,
    )


@router.post("", response_model=ScenarioSchema, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    scenario_data: ScenarioCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    if not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    new_scenario = Scenario(
        user_id=current_user.id,
        name=scenario_data.name,
        schedule=scenario_data.schedule,
        is_active=scenario_data.is_active,
    )

    node_map = _build_steps_from_nodes(scenario_data.nodes)
    new_scenario.steps = list(node_map.values())
    db.add(new_scenario)
    await db.flush()

    _apply_edges(node_map, scenario_data.edges)
    new_scenario.first_step_id = _find_start_step(node_map, scenario_data.nodes)

    await db.commit()

    await db.refresh(new_scenario)
    await db.refresh(new_scenario, attribute_names=["steps"])
    # -------------------------

    nodes, edges = _db_to_graph(new_scenario)
    return ScenarioSchema(
        id=new_scenario.id,
        name=new_scenario.name,
        schedule=new_scenario.schedule,
        is_active=new_scenario.is_active,
        nodes=nodes,
        edges=edges,
    )



@router.put("/{scenario_id}", response_model=ScenarioSchema)
async def update_scenario(
    scenario_id: int,
    scenario_data: ScenarioUpdate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Scenario)
        .where(Scenario.id == scenario_id, Scenario.user_id == current_user.id)
        .options(selectinload(Scenario.steps))
    )
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")

    if scenario_data.schedule and not croniter.is_valid(scenario_data.schedule):
        raise HTTPException(status_code=400, detail="Неверный формат CRON-строки.")

    # обновляем базовые поля
    db_scenario.name = scenario_data.name or db_scenario.name
    db_scenario.schedule = scenario_data.schedule or db_scenario.schedule
    db_scenario.is_active = (
        scenario_data.is_active
        if scenario_data.is_active is not None
        else db_scenario.is_active
    )

    # удаляем старые шаги, если новые переданы
    if scenario_data.nodes is not None:

        db_scenario.first_step_id = None
        
        for old_step in db_scenario.steps:
            await db.delete(old_step)
        await db.flush()

        # строим новые шаги
        node_map = _build_steps_from_nodes(scenario_data.nodes)
        db_scenario.steps = list(node_map.values())
        await db.flush()

        # проставляем связи
        _apply_edges(node_map, scenario_data.edges or [])

        # находим и устанавливаем ID нового стартового шага
        new_start_step_obj = next((step for step in node_map.values() if step.details.get("action_type") == "start"), None)
        if new_start_step_obj:
            db_scenario.first_step_id = new_start_step_obj.id

    await db.commit()

    await db.refresh(db_scenario)
    await db.refresh(db_scenario, attribute_names=["steps"])

    nodes, edges = _db_to_graph(db_scenario)
    return ScenarioSchema(
        id=db_scenario.id,
        name=db_scenario.name,
        schedule=db_scenario.schedule,
        is_active=db_scenario.is_active,
        nodes=nodes,
        edges=edges,
    )


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Scenario).where(
        Scenario.id == scenario_id, Scenario.user_id == current_user.id
    )
    result = await db.execute(stmt)
    db_scenario = result.scalar_one_or_none()
    if not db_scenario:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")

    # <<< ИЗМЕНЕНИЕ ЗДЕСЬ: РАЗРЫВАЕМ СВЯЗЬ ПЕРЕД УДАЛЕНИЕМ >>>
    # Это гарантирует, что база данных не будет блокировать удаление шагов.
    db_scenario.first_step_id = None
    await db.flush()  # Отправляем изменение в БД до основного удаления

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
from app.api.dependencies import get_current_active_profile
from app.api.schemas.stats import (
    FriendsAnalyticsResponse, ActivityStatsResponse, DailyActivity,
    FriendsDynamicResponse, FriendsDynamicItem
)
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data

router = APIRouter()

@router.get("/friends-analytics", response_model=FriendsAnalyticsResponse)
@cache(expire=3600) # Кешируем на 1 час
async def get_friends_analytics(current_user: User = Depends(get_current_active_profile)):
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
    current_user: User = Depends(get_current_active_profile)
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
from fastapi import APIRouter, Depends, Query, HTTPException, status, Body
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Union
from pydantic import BaseModel
from arq.connections import ArqRedis

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile, get_arq_pool
from app.db.session import get_db
from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest,
    TaskConfigResponse, TaskField
)
from app.api.schemas.tasks import ActionResponse, PaginatedTasksResponse
from app.core.plans import get_plan_config, is_feature_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import TaskKey

router = APIRouter()

AnyTaskRequest = Union[
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest
]

# Карта задач теперь связывает ключ с именем функции в ARQ
TASK_FUNC_MAP = {
    TaskKey.ACCEPT_FRIENDS: "accept_friend_requests_task",
    TaskKey.LIKE_FEED: "like_feed_task",
    TaskKey.ADD_RECOMMENDED: "add_recommended_friends_task",
    TaskKey.VIEW_STORIES: "view_stories_task",
    TaskKey.REMOVE_FRIENDS: "remove_friends_by_criteria_task",
    TaskKey.MASS_MESSAGING: "mass_messaging_task",
    TaskKey.JOIN_GROUPS: "join_groups_by_criteria_task",
    TaskKey.LEAVE_GROUPS: "leave_groups_by_criteria_task",
    TaskKey.BIRTHDAY_CONGRATULATION: "birthday_congratulation_task",
    TaskKey.ETERNAL_ONLINE: "eternal_online_task",
}

async def _enqueue_task(
    user: User, db: AsyncSession, arq_pool: ArqRedis, task_key: str, request_data: BaseModel, original_task_name: Optional[str] = None
):
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

    task_func_name = TASK_FUNC_MAP.get(TaskKey(task_key))
    if not task_func_name:
        raise HTTPException(status_code=404, detail="Задача не найдена.")

    task_display_name = original_task_name
    if not task_display_name:
        task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key), None)
        task_display_name = task_config.name if task_config else "Неизвестная задача"

    task_history = TaskHistory(
        user_id=user.id,
        task_name=task_display_name,
        status="PENDING",
        parameters=request_data.model_dump(exclude_unset=True)
    )
    db.add(task_history)
    await db.commit()
    await db.refresh(task_history)

    job = await arq_pool.enqueue_job(
        task_func_name,
        task_history_id=task_history.id,
        # ARQ требует, чтобы все аргументы были именованными
        **request_data.model_dump()
    )

    # Сохраняем ID задачи ARQ для возможной отмены в будущем
    task_history.celery_task_id = job.job_id
    await db.commit()

    return ActionResponse(
        message=f"Задача '{task_display_name}' успешно добавлена в очередь.",
        task_id=job.job_id
    )

@router.get("/{task_key}/config", response_model=TaskConfigResponse, summary="Получить конфигурацию для задачи")
async def get_task_config(task_key: TaskKey, current_user: User = Depends(get_current_active_profile)):
    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key.value), None)
    if not task_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конфигурация для задачи не найдена.")

    user_limits = get_plan_config(current_user.plan).get("limits", {})
    fields = []

    if task_config.has_count_slider:
        max_val = 1000
        if task_key == TaskKey.ADD_RECOMMENDED:
            max_val = user_limits.get("daily_add_friends_limit", 40)
        elif task_key == TaskKey.LIKE_FEED:
            max_val = user_limits.get("daily_likes_limit", 1000)

        fields.append(TaskField(
            name="count",
            type="slider",
            label=task_config.modal_count_label or "Количество",
            default_value=task_config.default_count or 20,
            max_value=max_val
        ))

    return TaskConfigResponse(
        display_name=task_config.name,
        has_filters=task_config.has_filters,
        fields=fields
    )

@router.post("/run/{task_key}", response_model=ActionResponse)
async def run_any_task(
    task_key: TaskKey,
    request_data: AnyTaskRequest = Body(...),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    return await _enqueue_task(current_user, db, arq_pool, task_key.value, request_data)

@router.get("/history", response_model=PaginatedTasksResponse)
async def get_user_task_history(
    current_user: User = Depends(get_current_active_profile),
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
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status not in ["PENDING", "STARTED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отменить можно только задачи в очереди или в процессе выполнения.")

    if task.celery_task_id:
        try:
            # Пытаемся отменить задачу в ARQ
            await arq_pool.abort_job(task.celery_task_id)
        except Exception as e:
            # Если задача уже не существует в Redis (например, уже выполнилась),
            # ARQ может выдать ошибку. Мы ее игнорируем.
            print(f"Ошибка при отмене задачи в ARQ (возможно, она уже завершилась): {e}")

    task.status = "CANCELLED"
    task.result = "Задача отменена пользователем."
    await db.commit()
    return {"message": "Запрос на отмену задачи отправлен."}

# <--- ИЗМЕНЕНИЕ: Реализация повтора задачи для ARQ --->
@router.post("/{task_history_id}/retry", response_model=ActionResponse)
async def retry_task(
    task_history_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    task = await db.get(TaskHistory, task_history_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")

    if task.status != "FAILURE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Повторить можно только задачу, завершившуюся с ошибкой.")

    task_key_str = next((item.id for item in AUTOMATIONS_CONFIG if item.name == task.task_name), None)
    if not task_key_str:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось определить тип задачи для повторного запуска.")

    # Получаем правильную Pydantic модель для валидации
    request_model_map = {
        TaskKey.ACCEPT_FRIENDS: AcceptFriendsRequest, TaskKey.LIKE_FEED: LikeFeedRequest,
        TaskKey.ADD_RECOMMENDED: AddFriendsRequest, TaskKey.VIEW_STORIES: EmptyRequest,
        TaskKey.REMOVE_FRIENDS: RemoveFriendsRequest, TaskKey.MASS_MESSAGING: MassMessagingRequest,
        TaskKey.JOIN_GROUPS: JoinGroupsRequest, TaskKey.LEAVE_GROUPS: LeaveGroupsRequest
    }
    RequestModel = request_model_map.get(TaskKey(task_key_str))
    if not RequestModel:
        raise HTTPException(status_code=500, detail="Не найдена модель запроса для задачи.")

    # Создаем новую задачу, используя параметры из старой
    validated_data = RequestModel(**(task.parameters or {}))

    return await _enqueue_task(
        current_user, db, arq_pool, task_key_str, validated_data, original_task_name=task.task_name
    )

# --- backend/app\api\endpoints\teams.py ---

# backend/app/api/endpoints/teams.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, delete
from typing import List

from app.db.session import get_db
from app.db.models import User, Team, TeamMember, ManagedProfile, TeamProfileAccess
from app.api.dependencies import get_current_manager_user
from app.api.schemas.teams import TeamRead, InviteMemberRequest, UpdateAccessRequest, TeamMemberRead, ProfileInfo, TeamMemberAccess
from app.core.plans import is_feature_available_for_plan, get_plan_config
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.core.constants import FeatureKey
import structlog

log = structlog.get_logger(__name__)
router = APIRouter()

async def check_agency_plan(manager: User = Depends(get_current_manager_user)):
    if not is_feature_available_for_plan(manager.plan, FeatureKey.AGENCY_MODE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Управление командой доступно только на тарифе 'Agency'."
        )
    return manager

async def get_team_owner(manager: User = Depends(check_agency_plan), db: AsyncSession = Depends(get_db)):
    stmt = select(Team).where(Team.owner_id == manager.id)
    team = (await db.execute(stmt)).scalar_one_or_none()
    if not team:
        team = Team(name=f"Команда {manager.id}", owner_id=manager.id)
        db.add(team)
        await db.commit()
        await db.refresh(team)
    return manager, team

@router.get("/my-team", response_model=TeamRead)
async def get_my_team(
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    manager, team = manager_and_team
    
    stmt = (
        select(Team)
        .options(
            selectinload(Team.members).selectinload(TeamMember.user),
            selectinload(Team.members).selectinload(TeamMember.profile_accesses)
        )
        .where(Team.id == team.id)
    )
    team_details = (await db.execute(stmt)).scalar_one()

    managed_profiles_db = (await db.execute(
        select(ManagedProfile)
        .options(selectinload(ManagedProfile.profile))
        .where(ManagedProfile.manager_user_id == manager.id)
    )).scalars().all()
    
    all_profiles_map = {mp.profile_user_id: mp.profile for mp in managed_profiles_db}
    
    # --- РЕШЕНИЕ ПРОБЛЕМЫ N+1 ---
    # 1. Собираем все уникальные VK ID, информацию о которых нужно запросить
    all_vk_ids_to_fetch = set()
    for member in team_details.members:
        all_vk_ids_to_fetch.add(member.user.vk_id)
    for profile in all_profiles_map.values():
        all_vk_ids_to_fetch.add(profile.vk_id)

    # 2. Делаем один-единственный пакетный запрос к VK API
    vk_info_map = {}
    if all_vk_ids_to_fetch:
        vk_api = VKAPI(decrypt_data(manager.encrypted_vk_token))
        vk_ids_str = ",".join(map(str, all_vk_ids_to_fetch))
        user_infos = await vk_api.get_user_info(user_ids=vk_ids_str, fields="photo_50")
        if user_infos:
            vk_info_map = {info['id']: info for info in user_infos}

    # 3. Собираем ответ, используя предзагруженные данные из vk_info_map
    members_response = []
    for member in team_details.members:
        member_vk_info = vk_info_map.get(member.user.vk_id, {})
        
        accesses = []
        member_access_map = {pa.profile_user_id for pa in member.profile_accesses}
        
        for profile in all_profiles_map.values():
            profile_vk_info = vk_info_map.get(profile.vk_id, {})
            accesses.append(TeamMemberAccess(
                profile=ProfileInfo(
                    id=profile.id, vk_id=profile.vk_id,
                    first_name=profile_vk_info.get("first_name", "N/A"),
                    last_name=profile_vk_info.get("last_name", ""),
                    photo_50=profile_vk_info.get("photo_50", "")
                ),
                has_access=profile.id in member_access_map
            ))
            
        members_response.append(TeamMemberRead(
            id=member.id, user_id=member.user_id, role=member.role.value,
            user_info=ProfileInfo(
                id=member.user.id, vk_id=member.user.vk_id,
                first_name=member_vk_info.get("first_name", "N/A"),
                last_name=member_vk_info.get("last_name", ""),
                photo_50=member_vk_info.get("photo_50", "")
            ),
            accesses=accesses
        ))
    
    return TeamRead(id=team.id, name=team.name, owner_id=team.owner_id, members=members_response)


@router.post("/my-team/members", status_code=status.HTTP_201_CREATED)
async def invite_member(
    invite_data: InviteMemberRequest,
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    manager, team = manager_and_team
    
    # Загружаем актуальное количество участников
    await db.refresh(team, attribute_names=['members'])

    plan_config = get_plan_config(manager.plan)
    max_members = plan_config.get("limits", {}).get("max_team_members", 1)
    if len(team.members) >= max_members:
        raise HTTPException(status_code=403, detail=f"Достигнут лимит на количество участников в команде ({max_members}).")

    invited_user = (await db.execute(select(User).where(User.vk_id == invite_data.user_vk_id))).scalar_one_or_none()
    if not invited_user:
        raise HTTPException(status_code=404, detail="Пользователь с таким VK ID не найден в системе Zenith.")
    
    stmt_check_member = select(TeamMember).where(TeamMember.user_id == invited_user.id)
    existing_membership = (await db.execute(stmt_check_member)).scalar_one_or_none()
    if existing_membership:
        raise HTTPException(status_code=409, detail="Этот пользователь уже состоит в команде.")

    new_member = TeamMember(team_id=team.id, user_id=invited_user.id)
    db.add(new_member)
    await db.commit()
    return {"message": "Пользователь успешно добавлен в команду."}

@router.delete("/my-team/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: int,
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    _, team = manager_and_team
    member = (await db.execute(select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == team.id))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Участник команды не найден.")
    if member.user_id == team.owner_id:
        raise HTTPException(status_code=400, detail="Нельзя удалить владельца команды.")
        
    await db.delete(member)
    await db.commit()

@router.put("/my-team/members/{member_id}/access")
async def update_member_access(
    member_id: int,
    access_data: List[UpdateAccessRequest],
    manager_and_team: tuple = Depends(get_team_owner),
    db: AsyncSession = Depends(get_db)
):
    manager, team = manager_and_team
    member = (await db.execute(select(TeamMember).where(TeamMember.id == member_id, TeamMember.team_id == team.id))).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Участник команды не найден.")

    # Проверяем, что все profile_user_id принадлежат менеджеру
    managed_profiles_stmt = select(ManagedProfile.profile_user_id).where(ManagedProfile.manager_user_id == manager.id)
    managed_ids = (await db.execute(managed_profiles_stmt)).scalars().all()
    
    for access in access_data:
        if access.profile_user_id not in managed_ids and access.profile_user_id != manager.id:
            raise HTTPException(status_code=403, detail=f"Доступ к профилю {access.profile_user_id} не может быть предоставлен.")

    await db.execute(delete(TeamProfileAccess).where(TeamProfileAccess.team_member_id == member_id))
    
    accesses_to_add = [
        TeamProfileAccess(team_member_id=member_id, profile_user_id=access.profile_user_id)
        for access in access_data if access.has_access
    ]
    
    if accesses_to_add:
        db.add_all(accesses_to_add)
        
    await db.commit()
    return {"message": "Права доступа обновлены."}

# --- backend/app\api\endpoints\users.py ---

# backend/app/api/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from app.db.session import get_db
from app.db.models import ManagedProfile, User, DelayProfile, FilterPreset
from app.api.dependencies import get_current_active_profile, get_current_manager_user
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository
from app.core.plans import get_features_for_plan, is_feature_available_for_plan
from app.api.schemas.users import TaskInfoResponse, FilterPresetCreate, FilterPresetRead
from app.core.constants import PlanName, FeatureKey

router = APIRouter()

class UserMeResponse(BaseModel):
    id: int
    vk_id: int
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
async def read_users_me(current_user: User = Depends(get_current_active_profile)):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    if not vk_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Токен доступа недействителен. Пожалуйста, авторизуйтесь заново."
        )
        
    vk_api = VKAPI(access_token=vk_token)
    
    try:
        user_info_vk_list = await vk_api.get_user_info(fields="photo_200,status,counters")
        user_info_vk = user_info_vk_list[0] if user_info_vk_list else {}
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
        plan_name = PlanName.EXPIRED

    features = get_features_for_plan(plan_name)
    
    return {
        **user_info_vk,
        "id": current_user.id,
        "vk_id": current_user.vk_id,
        "plan": current_user.plan,
        "plan_expires_at": current_user.plan_expires_at,
        "is_admin": current_user.is_admin,
        "delay_profile": current_user.delay_profile.value,
        "is_plan_active": is_plan_active,
        "available_features": features,
    }

@router.get("/me/limits", response_model=DailyLimitsResponse)
async def get_daily_limits(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
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
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    if request_data.delay_profile != DelayProfile.normal and not is_feature_available_for_plan(current_user.plan, FeatureKey.FAST_SLOW_DELAY_PROFILE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Смена скорости доступна только на PRO тарифе.")
        
    current_user.delay_profile = request_data.delay_profile
    await db.commit()
    await db.refresh(current_user)
    return await read_users_me(current_user)

@router.get("/task-info", response_model=TaskInfoResponse)
async def get_task_info(
    task_key: str = Query(...),
    current_user: User = Depends(get_current_active_profile)
):
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    vk_api = VKAPI(access_token=vk_token)
    count = 0

    try:
        if task_key == "accept_friends":
            response = await vk_api.get_incoming_friend_requests()
            count = response.get("count", 0) if response else 0
        
        elif task_key == "remove_friends":
            user_info_list = await vk_api.get_user_info(user_ids=str(current_user.vk_id), fields="counters")
            if user_info_list:
                user_info = user_info_list[0]
                count = user_info.get("counters", {}).get("friends", 0)

    except VKAPIError as e:
        # Логируем ошибку, но не прерываем работу, возвращаем 0
        print(f"Could not fetch task info for {task_key} due to VK API error: {e}")
        count = 0

    return TaskInfoResponse(count=count)

@router.get("/me/filter-presets", response_model=List[FilterPresetRead])
async def get_filter_presets(
    action_type: str = Query(...),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(FilterPreset).where(
        FilterPreset.user_id == current_user.id,
        FilterPreset.action_type == action_type
    ).order_by(FilterPreset.name)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/me/filter-presets", response_model=FilterPresetRead, status_code=status.HTTP_201_CREATED)
async def create_filter_preset(
    preset_data: FilterPresetCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    new_preset = FilterPreset(user_id=current_user.id, **preset_data.model_dump())
    db.add(new_preset)
    try:
        await db.commit()
        await db.refresh(new_preset)
        return new_preset
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пресет с таким названием для данного действия уже существует."
        )

@router.delete("/me/filter-presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter_preset(
    preset_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    stmt = delete(FilterPreset).where(
        FilterPreset.id == preset_id,
        FilterPreset.user_id == current_user.id
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пресет не найден.")
    await db.commit()


class ManagedProfileRead(BaseModel):
    id: int
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str
    
    class Config:
        from_attributes = True

@router.get("/me/managed-profiles", response_model=List[ManagedProfileRead], summary="Получить список профилей для переключения")
async def get_managed_profiles(
    manager: User = Depends(get_current_manager_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User)
        .options(selectinload(User.managed_profiles).selectinload(ManagedProfile.profile))
        .where(User.id == manager.id)
    )
    manager_with_profiles = result.scalar_one()

    all_users_map = {manager.id: manager}
    for rel in manager_with_profiles.managed_profiles:
        all_users_map[rel.profile.id] = rel.profile

    all_vk_ids = [user.vk_id for user in all_users_map.values()]
    vk_info_map = {}
    if all_vk_ids:
        vk_api = VKAPI(decrypt_data(manager.encrypted_vk_token))
        user_infos = await vk_api.get_user_info(user_ids=",".join(map(str, all_vk_ids)), fields="photo_50")
        if user_infos:
            vk_info_map = {info['id']: info for info in user_infos}

    profiles_info = []
    for user in all_users_map.values():
        vk_info = vk_info_map.get(user.vk_id, {})
        profiles_info.append({
            "id": user.id,
            "vk_id": user.vk_id,
            "first_name": vk_info.get("first_name", "N/A"),
            "last_name": vk_info.get("last_name", ""),
            "photo_50": vk_info.get("photo_50", "")
        })

    return sorted(profiles_info, key=lambda p: p['id'] != manager.id)

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
from .posts import router as posts_router  # <--- ВОТ ЭТА СТРОКА ДОБАВЛЕНА
from .teams import router as teams_router
from .websockets import router as websockets_router

# --- backend/app\api\schemas\actions.py ---

# --- backend/app/api/schemas/actions.py ---
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Any

# backend/app/api/schemas/actions.py
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Any

class ActionFilters(BaseModel):
    sex: Optional[Literal[0, 1, 2]] = Field(0, description="0 - любой, 1 - жен, 2 - муж")
    is_online: Optional[bool] = False
    last_seen_hours: Optional[int] = Field(None, ge=1)
    allow_closed_profiles: bool = False
    status_keyword: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    only_with_photo: Optional[bool] = Field(False)

    # Для remove_friends
    remove_banned: Optional[bool] = True
    last_seen_days: Optional[int] = Field(None, ge=1)
    
class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']

# ... (остальные модели без изменений) ...

class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']

# --- Модели для каждой задачи ---

class LikeFeedRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class AddFriendsRequest(BaseModel):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    like_config: LikeAfterAddConfig = Field(default_factory=LikeAfterAddConfig)
    send_message_on_add: bool = False
    message_text: Optional[str] = Field(None, max_length=500)

class AcceptFriendsRequest(BaseModel):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class RemoveFriendsRequest(BaseModel):
    count: int = Field(100, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class MassMessagingRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    message_text: str = Field(..., min_length=1, max_length=1000)
    only_new_dialogs: bool = Field(False, description="Отправлять только тем, с кем еще не было переписки.")

class LeaveGroupsRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class JoinGroupsRequest(BaseModel):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class EmptyRequest(BaseModel):
    pass

class BirthdayCongratulationRequest(BaseModel):
    message_template_default: str = "С Днем Рождения, {name}!"
    message_template_male: Optional[str] = None
    message_template_female: Optional[str] = None

# --- Для динамической конфигурации UI ---
class TaskField(BaseModel):
    name: str
    type: Literal["slider", "switch", "text"]
    label: str
    default_value: Any
    max_value: Optional[int] = None
    tooltip: Optional[str] = None

class TaskConfigResponse(BaseModel):
    display_name: str
    has_filters: bool
    fields: List[TaskField]

# --- backend/app\api\schemas\analytics.py ---

# --- backend/app/api/schemas/analytics.py ---
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

class ProfileSummaryResponse(BaseModel):
    friends: int
    followers: int
    photos: int
    wall_posts: int

class ProfileGrowthItem(BaseModel):
    date: date
    total_likes_on_content: int
    friends_count: int

class ProfileGrowthResponse(BaseModel):
    data: List[ProfileGrowthItem]

class FriendRequestConversionResponse(BaseModel):
    sent_total: int
    accepted_total: int
    conversion_rate: float = Field(..., ge=0, le=100)

class PostActivityHeatmapResponse(BaseModel):
    data: List[List[int]] = Field(..., description="Матрица 7x24, где data[day][hour] = уровень активности от 0 до 100")

# --- backend/app\api\schemas\auth.py ---

# backend/app/api/schemas/auth.py
from pydantic import BaseModel

class TokenRequest(BaseModel):
    vk_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class EnrichedTokenResponse(TokenResponse):
    """
    Ответ, который также возвращает ID пользователя и активного профиля,
    чтобы избавить фронтенд от необходимости декодировать JWT.
    """
    manager_id: int
    active_profile_id: int

# --- backend/app\api\schemas\billing.py ---

# --- backend/app/api/schemas/billing.py ---
from pydantic import BaseModel, Field
from typing import List, Optional

class PlanPeriod(BaseModel):
    """Схема для описания периода подписки и скидки."""
    months: int
    discount_percent: float

class PlanDetail(BaseModel):
    """Детальная информация о тарифном плане для отображения на фронтенде."""
    id: str = Field(..., description="Идентификатор плана (напр., 'Plus', 'PRO')")
    display_name: str = Field(..., description="Человекочитаемое название тарифа")
    price: float = Field(..., description="Цена тарифа за 1 месяц")
    currency: str = Field("RUB", description="Валюта")
    description: str = Field(..., description="Описание тарифа")
    features: List[str] = Field([], description="Список возможностей тарифа")
    is_popular: Optional[bool] = Field(False, description="Является ли тариф популярным выбором")
    periods: List[PlanPeriod] = Field([], description="Доступные периоды подписки со скидками")

class AvailablePlansResponse(BaseModel):
    """Ответ со списком доступных для покупки планов."""
    plans: List[PlanDetail]

class CreatePaymentRequest(BaseModel):
    """
    Схема для создания платежа.
    ИСПРАВЛЕНО: Поля plan_id и months соответствуют логике эндпоинта.
    """
    plan_id: str = Field(..., description="Идентификатор тарифа для покупки (напр., 'Plus')")
    months: int = Field(..., ge=1, description="Количество месяцев для покупки")

class CreatePaymentResponse(BaseModel):
    confirmation_url: str

# --- backend/app\api\schemas\notifications.py ---

# --- backend/app/api/schemas/notifications.py ---
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List

class Notification(BaseModel):
    id: int
    message: str
    level: str
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class NotificationsResponse(BaseModel):
    items: List[Notification]
    unread_count: int

# --- backend/app\api\schemas\posts.py ---

# --- backend/app/api/schemas/posts.py ---
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List, Optional

class PostBase(BaseModel):
    post_text: Optional[str] = None
    attachments: Optional[List[str]] = Field(default_factory=list)
    publish_at: datetime

class PostCreate(PostBase):
    pass

class PostUpdate(PostBase):
    pass

class PostRead(PostBase):
    id: int
    vk_profile_id: int
    status: str
    vk_post_id: Optional[str] = None
    error_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UploadedImageResponse(BaseModel):
    attachment_id: str

# --- backend/app\api\schemas\proxies.py ---

# --- backend/app/api/schemas/proxies.py ---
from pydantic import BaseModel, Field, ConfigDict
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
    model_config = ConfigDict(from_attributes=True)

class ProxyTestResponse(BaseModel):
    is_working: bool
    status_message: str

# --- backend/app\api\schemas\scenarios.py ---

# --- backend/app/api/schemas/scenarios.py ---
import enum
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional

class ScenarioStepType(str, enum.Enum):
    action = "action"
    condition = "condition"

class ScenarioStepNode(BaseModel):
    id: str
    # ИЗМЕНЕНИЕ: Добавляем 'start' в возможные типы
    type: str # Должно быть Literal['start', 'action', 'condition'], но для простоты оставим str
    data: Dict[str, Any]
    position: Dict[str, float]

class ScenarioEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None # 'next', 'on_success', 'on_failure'

# --- Схемы для сценариев ---
class ScenarioBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    schedule: str = Field(..., description="CRON-строка, напр. '0 9 * * 1-5'")
    is_active: bool = False

class ScenarioCreate(ScenarioBase):
    nodes: List[ScenarioStepNode]
    edges: List[ScenarioEdge]

class ScenarioUpdate(ScenarioCreate):
    pass

class Scenario(ScenarioBase):
    id: int
    nodes: List[ScenarioStepNode]
    edges: List[ScenarioEdge]
    model_config = ConfigDict(from_attributes=True)

# Схема для нового эндпоинта
class ConditionOption(BaseModel):
    value: str
    label: str

class AvailableCondition(BaseModel):
    key: str
    label: str
    type: str # 'number', 'select', 'time'
    operators: List[str]
    options: Optional[List[ConditionOption]] = None

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

# --- backend/app\api\schemas\teams.py ---

# --- backend/app/api/schemas/teams.py ---
from pydantic import BaseModel, Field, ConfigDict
from typing import List

class ProfileInfo(BaseModel):
    id: int
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str
    model_config = ConfigDict(from_attributes=True)

class TeamMemberAccess(BaseModel):
    profile: ProfileInfo
    has_access: bool
    
    # ДОБАВЛЕНО: Для корректной работы с ORM-моделями
    model_config = ConfigDict(from_attributes=True)

class TeamMemberRead(BaseModel):
    id: int
    user_id: int
    user_info: ProfileInfo
    role: str
    accesses: List[TeamMemberAccess]
    model_config = ConfigDict(from_attributes=True)

class TeamRead(BaseModel):
    id: int
    name: str
    owner_id: int
    members: List[TeamMemberRead]
    model_config = ConfigDict(from_attributes=True)

class TeamCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)

class InviteMemberRequest(BaseModel):
    user_vk_id: int

class UpdateAccessRequest(BaseModel):
    profile_user_id: int
    has_access: bool

# --- backend/app\api\schemas\users.py ---

# --- backend/app/api/schemas/users.py ---
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any

class UserBase(BaseModel):
    id: int
    vk_id: int
    model_config = ConfigDict(from_attributes=True)

class TaskInfoResponse(BaseModel):
    count: int

class FilterPresetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    action_type: str
    filters: Dict[str, Any]

class FilterPresetCreate(FilterPresetBase):
    pass

class FilterPresetRead(FilterPresetBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class ManagedProfileRead(BaseModel):
    id: int
    vk_id: int
    first_name: str
    last_name: str
    photo_50: str
    model_config = ConfigDict(from_attributes=True)

# --- backend/app\api\schemas\__init__.py ---



# --- backend/app\core\config.py ---

# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

# --- ИЗМЕНЕНИЕ: Определяем абсолютный путь к .env файлу ---
# Это гарантирует, что .env будет найден, независимо от точки запуска приложения.
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

    VK_HEALTH_CHECK_TOKEN: Optional[str] = None
    VK_TEST_USER_ID: Optional[str] = None
    VK_TEST_FRIEND_ID: Optional[str] = None

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
from app.core.schemas.config import PlanConfig, AutomationConfig

# Определяем путь к директории с конфигами относительно текущего файла
CONFIG_PATH = Path(__file__).parent / "configs"

@lru_cache(maxsize=1)
def load_plans_config() -> dict[str, PlanConfig]:
    """
    Загружает, валидирует через Pydantic и кеширует конфигурацию тарифных планов.
    Возвращает словарь, где ключ - ID тарифа, значение - Pydantic модель.
    """
    config_file = CONFIG_PATH / "plans.yml"
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    
    return {plan_id: PlanConfig(**data) for plan_id, data in raw_config.items()}

@lru_cache(maxsize=1)
def load_automations_config() -> list[AutomationConfig]:
    """
    Загружает, валидирует через Pydantic и кеширует конфигурацию типов автоматизаций.
    """
    config_file = CONFIG_PATH / "automations.yml"
    if not config_file.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
        
    return [AutomationConfig(**item) for item in raw_config]

# Загружаем конфиги при старте модуля, чтобы проверить их наличие и валидность
try:
    PLAN_CONFIG = load_plans_config()
    AUTOMATIONS_CONFIG = load_automations_config()
except (FileNotFoundError, Exception) as e:
    print(f"CRITICAL ERROR loading configs: {e}")
    # В реальном приложении здесь можно остановить запуск
    exit(1)

# --- backend/app\core\constants.py ---

# backend/app/core/constants.py
from enum import Enum

class PlanName(str, Enum):
    BASE = "Базовый"
    PLUS = "Plus"
    PRO = "PRO"
    AGENCY = "Agency"
    EXPIRED = "Expired"

class FeatureKey(str, Enum):
    PROXY_MANAGEMENT = "proxy_management"
    SCENARIOS = "scenarios"
    PROFILE_GROWTH_ANALYTICS = "profile_growth_analytics"
    FAST_SLOW_DELAY_PROFILE = "fast_slow_delay_profile"
    AUTOMATIONS_CENTER = "automations_center"
    AGENCY_MODE = "agency_mode"
    POST_SCHEDULER = "post_scheduler"

class TaskKey(str, Enum):
    ACCEPT_FRIENDS = "accept_friends"
    LIKE_FEED = "like_feed"
    ADD_RECOMMENDED = "add_recommended"
    VIEW_STORIES = "view_stories"
    REMOVE_FRIENDS = "remove_friends"
    MASS_MESSAGING = "mass_messaging"
    LEAVE_GROUPS = "leave_groups"
    JOIN_GROUPS = "join_groups"
    BIRTHDAY_CONGRATULATION = "birthday_congratulation"
    ETERNAL_ONLINE = "eternal_online"

class AutomationGroup(str, Enum):
    STANDARD = "standard"
    ONLINE = "online"
    CONTENT = "content"

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
from functools import lru_cache
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG
from app.core.constants import PlanName, FeatureKey, TaskKey

@lru_cache(maxsize=16)
def get_plan_config(plan_name: PlanName | str) -> dict:
    """Безопасно получает конфигурацию плана, возвращая 'Expired' если план не найден."""
    plan_model = PLAN_CONFIG.get(str(plan_name), PLAN_CONFIG[PlanName.EXPIRED])
    return plan_model.model_dump()

def get_limits_for_plan(plan_name: PlanName | str) -> dict:
    """Возвращает словарь с лимитами для указанного плана."""
    plan_data = get_plan_config(plan_name)
    return plan_data.get("limits", {}).copy()

@lru_cache(maxsize=1)
def get_all_feature_keys() -> list[str]:
    """Возвращает список всех возможных ключей фич из конфига."""
    automation_ids = [item.id for item in AUTOMATIONS_CONFIG]
    
    other_features = [
        FeatureKey.PROXY_MANAGEMENT, 
        FeatureKey.SCENARIOS, 
        FeatureKey.PROFILE_GROWTH_ANALYTICS, 
        FeatureKey.FAST_SLOW_DELAY_PROFILE,
        FeatureKey.AUTOMATIONS_CENTER,
        FeatureKey.AGENCY_MODE,
        FeatureKey.POST_SCHEDULER,
    ]
    return list(set(automation_ids + [f.value for f in other_features]))

@lru_cache(maxsize=256)
def is_feature_available_for_plan(plan_name: PlanName | str, feature_id: str) -> bool:
    """Проверяет, доступна ли указанная фича для данного тарифного плана."""
    plan_model = PLAN_CONFIG.get(str(plan_name), PLAN_CONFIG[PlanName.EXPIRED])
    available_features = plan_model.available_features
    
    if available_features == "*":
        return True
    
    return feature_id in available_features

def get_features_for_plan(plan_name: PlanName | str) -> list[str]:
    """
    Возвращает полный список доступных ключей фич для тарифного плана.
    Обрабатывает wildcard '*' для PRO тарифов.
    """
    plan_model = PLAN_CONFIG.get(str(plan_name), PLAN_CONFIG[PlanName.EXPIRED])
    available = plan_model.available_features
    
    if available == "*":
        return get_all_feature_keys()
    
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



# --- backend/app\core\schemas\config.py ---

# backend/app/core/schemas/config.py
from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class AutomationConfig(BaseModel):
    id: str
    name: str
    description: str
    has_filters: bool
    has_count_slider: bool
    modal_count_label: Optional[str] = None
    default_count: Optional[int] = None
    group: Optional[Literal["standard", "online", "content"]] = "standard"

class PlanPeriod(BaseModel):
    months: int = Field(..., gt=0)
    discount_percent: float = Field(..., ge=0, le=100)

class PlanLimits(BaseModel):
    daily_likes_limit: int = Field(..., ge=0)
    daily_add_friends_limit: int = Field(..., ge=0)
    max_concurrent_tasks: int = Field(..., ge=1)
    max_profiles: Optional[int] = Field(None, ge=1)
    max_team_members: Optional[int] = Field(None, ge=1)

class PlanConfig(BaseModel):
    display_name: str
    description: str
    limits: PlanLimits
    available_features: List[str] | Literal["*"]
    base_price: Optional[float] = Field(None, ge=0)
    is_popular: Optional[bool] = False
    periods: Optional[List[PlanPeriod]] = []
    features: Optional[List[str]] = []

# --- backend/app\db\base.py ---

# backend/app/db/base.py
from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

# ДОБАВЛЕНО: Стандартное соглашение об именовании для Alembic и SQLAlchemy.
# Это решает проблемы с безымянными и ненайденными ограничениями (constraints).
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# ИЗМЕНЕНИЕ: Передаем metadata с соглашением в declarative_base
Base = declarative_base(metadata=MetaData(naming_convention=convention))

# --- backend/app\db\enums.py ---

import enum

class DelayProfile(enum.Enum):
    slow = "slow"
    normal = "normal"
    fast = "fast"

class TeamMemberRole(enum.Enum):
    admin = "admin"
    member = "member"

class ScenarioStepType(enum.Enum):
    action = "action"
    condition = "condition"

class ScheduledPostStatus(enum.Enum):
    scheduled = "scheduled"
    published = "published"
    failed = "failed"

class FriendRequestStatus(enum.Enum):
    pending = "pending"
    accepted = "accepted"

# --- backend/app\db\session.py ---

# backend/app/db/session.py

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
# --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
from sqlalchemy.pool import NullPool
# ------------------------------

from app.core.config import settings

# --- ИЗМЕНИТЕ СОЗДАНИЕ ENGINE, ДОБАВИВ poolclass=NullPool ---
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    poolclass=NullPool  # <-- Вот это изменение
)
# -----------------------------------------------------------

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



# --- backend/app\db\models\analytics.py ---

import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, JSON, Index, Date, Enum
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.enums import FriendRequestStatus

class DailyStats(Base):
    __tablename__ = "daily_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, default=datetime.date.today, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
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

class WeeklyStats(Base):
    __tablename__ = "weekly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_identifier = Column(String, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    user = relationship("User")
    __table_args__ = (UniqueConstraint('user_id', 'week_identifier', name='_user_week_uc'),)

class MonthlyStats(Base):
    __tablename__ = "monthly_stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month_identifier = Column(String, nullable=False)
    likes_count = Column(Integer, default=0, nullable=False)
    friends_added_count = Column(Integer, default=0, nullable=False)
    friend_requests_accepted_count = Column(Integer, default=0, nullable=False)
    user = relationship("User")
    __table_args__ = (UniqueConstraint('user_id', 'month_identifier', name='_user_month_uc'),)

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

class PostActivityHeatmap(Base):
    __tablename__ = "post_activity_heatmaps"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True)
    heatmap_data = Column(JSON, nullable=False)
    last_updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = relationship("User", back_populates="heatmap")

class FriendRequestLog(Base):
    __tablename__ = "friend_request_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_vk_id = Column(BigInteger, nullable=False, index=True)
    status = Column(Enum(FriendRequestStatus), nullable=False, default=FriendRequestStatus.pending, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="friend_requests")
    __table_args__ = (UniqueConstraint('user_id', 'target_vk_id', name='_user_target_uc'),)

# --- backend/app\db\models\payment.py ---

import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.db.base import Base

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    payment_system_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending", nullable=False)
    plan_name = Column(String, nullable=False)
    months = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = relationship("User")

# --- backend/app\db\models\shared.py ---

import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    UniqueConstraint, Boolean, JSON,
)
from sqlalchemy.orm import relationship
from app.db.base import Base

class Proxy(Base):
    __tablename__ = "proxies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    encrypted_proxy_url = Column(String, nullable=False)
    is_working = Column(Boolean, default=True, nullable=False, index=True)
    last_checked_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    check_status_message = Column(String, nullable=True)
    user = relationship("User", back_populates="proxies")
    __table_args__ = (UniqueConstraint('user_id', 'encrypted_proxy_url', name='_user_proxy_uc'),)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(String, nullable=False)
    level = Column(String, default="info", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, index=True)
    user = relationship("User", back_populates="notifications")

class FilterPreset(Base):
    __tablename__ = "filter_presets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    action_type = Column(String, nullable=False, index=True)
    filters = Column(JSON, nullable=False)
    user = relationship("User", back_populates="filter_presets")
    __table_args__ = (UniqueConstraint('user_id', 'name', 'action_type', name='_user_name_action_uc'),)


# --- backend/app\db\models\task.py ---

from datetime import datetime, UTC
import enum
from sqlalchemy import (
    Column, ForeignKeyConstraint, Integer, String, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, Boolean, JSON, Text, Enum, Index, Float
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.enums import ScenarioStepType, ScheduledPostStatus

class ScenarioStepType(enum.Enum):
    action = "action"
    condition = "condition"

class ScheduledPostStatus(enum.Enum):
    scheduled = "scheduled"
    published = "published"
    failed = "failed"

class TaskHistory(Base):
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    celery_task_id = Column(String, unique=True, nullable=True, index=True)
    task_name = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING", nullable=False, index=True)
    parameters = Column(JSON, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    user = relationship("User", back_populates="task_history")
    __table_args__ = (Index('ix_task_history_user_status', 'user_id', 'status'),)

class Automation(Base):
    __tablename__ = "automations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_type = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=False, nullable=False)
    settings = Column(JSON, nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="automations")
    __table_args__ = (UniqueConstraint('user_id', 'automation_type', name='_user_automation_uc'),)

class Scenario(Base):
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    schedule = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    
    # --- ИЗМЕНЕНИЕ: Столбец для ID, а не сама связь ---
    first_step_id = Column(Integer, nullable=True)

    # Отношения
    user = relationship("User", back_populates="scenarios")
    steps = relationship(
        "ScenarioStep", 
        back_populates="scenario", 
        cascade="all, delete-orphan", 
        foreign_keys="[ScenarioStep.scenario_id]"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ['first_step_id'], 
            ['scenario_steps.id'],
            use_alter=True, 
            name="fk_scenarios_first_step_id_scenario_steps"
        ),
    )

class ScenarioStep(Base):
    __tablename__ = "scenario_steps"
    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    step_type = Column(Enum(ScenarioStepType), nullable=False)
    details = Column(JSON, nullable=False)
    next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True)
    on_success_next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True)
    on_failure_next_step_id = Column(Integer, ForeignKey("scenario_steps.id"), nullable=True)
    position_x = Column(Float, default=0)
    position_y = Column(Float, default=0)
    scenario = relationship("Scenario", back_populates="steps", foreign_keys=[scenario_id])

class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vk_profile_id = Column(BigInteger, nullable=False, index=True)
    post_text = Column(Text, nullable=True)
    attachments = Column(JSON, nullable=True)
    publish_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(ScheduledPostStatus), nullable=False, default=ScheduledPostStatus.scheduled, index=True)
    celery_task_id = Column(String, nullable=True, unique=True)
    vk_post_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    user = relationship("User", back_populates="scheduled_posts")

class SentCongratulation(Base):
    __tablename__ = "sent_congratulations"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_vk_id = Column(BigInteger, nullable=False, index=True)
    year = Column(Integer, nullable=False)
    user = relationship("User")
    __table_args__ = (UniqueConstraint('user_id', 'friend_vk_id', 'year', name='_user_friend_year_uc'),)

class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    user = relationship("User")

# --- backend/app\db\models\user.py ---

from datetime import datetime, UTC
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, Boolean, text, Enum, Text
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.db.enums import DelayProfile, TeamMemberRole

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    vk_id = Column(BigInteger, unique=True, index=True, nullable=False)
    encrypted_vk_token = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    plan = Column(String, nullable=False, server_default='Базовый')
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, nullable=False, server_default='false')
    daily_likes_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_add_friends_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_message_limit = Column(Integer, nullable=False, server_default=text('0'))
    delay_profile = Column(Enum(DelayProfile), nullable=False, server_default=DelayProfile.normal.name)

    # Связи остаются такими же
    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    task_history = relationship("TaskHistory", back_populates="user", cascade="all, delete-orphan")
    daily_stats = relationship("DailyStats", back_populates="user", cascade="all, delete-orphan")
    automations = relationship("Automation", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")
    profile_metrics = relationship("ProfileMetric", back_populates="user", cascade="all, delete-orphan")
    filter_presets = relationship("FilterPreset", back_populates="user", cascade="all, delete-orphan")
    friend_requests = relationship("FriendRequestLog", back_populates="user", cascade="all, delete-orphan")
    heatmap = relationship("PostActivityHeatmap", back_populates="user", uselist=False, cascade="all, delete-orphan")
    managed_profiles = relationship("ManagedProfile", foreign_keys="[ManagedProfile.manager_user_id]", back_populates="manager", cascade="all, delete-orphan")
    scheduled_posts = relationship("ScheduledPost", back_populates="user", cascade="all, delete-orphan", foreign_keys="[ScheduledPost.user_id]")
    owned_team = relationship("Team", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    team_membership = relationship("TeamMember", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    owner = relationship("User", back_populates="owned_team")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    role = Column(Enum(TeamMemberRole), nullable=False, default=TeamMemberRole.member)
    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_membership")
    profile_accesses = relationship("TeamProfileAccess", back_populates="team_member", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='_team_user_uc'),)

class TeamProfileAccess(Base):
    __tablename__ = "team_profile_access"
    id = Column(Integer, primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"), nullable=False)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_member = relationship("TeamMember", back_populates="profile_accesses")
    profile = relationship("User", foreign_keys=[profile_user_id])

class ManagedProfile(Base):
    __tablename__ = "managed_profiles"
    id = Column(Integer, primary_key=True)
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    manager = relationship("User", foreign_keys=[manager_user_id], back_populates="managed_profiles")
    profile = relationship("User", foreign_keys=[profile_user_id])
    __table_args__ = (UniqueConstraint('manager_user_id', 'profile_user_id', name='_manager_profile_uc'),)

class LoginHistory(Base):
    __tablename__ = "login_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    user = relationship("User")

# --- backend/app\db\models\__init__.py ---

# --- backend/app/db/models/__init__.py ---

# Этот файл собирает все модели из подмодулей в один неймспейс app.db.models
# Это позволяет использовать привычный импорт: from app.db.models import User

from .analytics import *
from .payment import *
from .shared import *
from .task import *
from .user import *

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

# --- backend/app/services/analytics_service.py ---
import datetime
import pytz
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import PostActivityHeatmap
from app.services.vk_api import VKAPIError
import structlog

log = structlog.get_logger(__name__)

class AnalyticsService(BaseVKService):

    async def generate_post_activity_heatmap(self):
        await self._initialize_vk_api()
        
        try:
            friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="last_seen")
        except VKAPIError as e:
            log.error("heatmap.vk_error", user_id=self.user.id, error=str(e))
            return
        
        if not friends:
            return

        # Инициализируем матрицу 7 дней x 24 часа нулями
        heatmap = [[0 for _ in range(24)] for _ in range(7)]
        
        now = datetime.datetime.utcnow()
        # Анализируем активность за последние 2 недели
        two_weeks_ago = now - datetime.timedelta(weeks=2)

        for friend in friends:
            last_seen_data = friend.get("last_seen")
            if not last_seen_data:
                continue
            
            seen_timestamp = last_seen_data.get("time")
            if not seen_timestamp:
                continue
            
            seen_time = datetime.datetime.fromtimestamp(seen_timestamp, tz=pytz.UTC)
            
            if seen_time > two_weeks_ago:
                day_of_week = seen_time.weekday() # 0 = Понедельник, 6 = Воскресенье
                hour_of_day = seen_time.hour
                heatmap[day_of_week][hour_of_day] += 1
        
        # Нормализуем данные, чтобы получить значения от 0 до 100 для удобства фронтенда
        max_activity = max(max(row) for row in heatmap)
        if max_activity > 0:
            normalized_heatmap = [
                [int((count / max_activity) * 100) for count in row]
                for row in heatmap
            ]
        else:
            normalized_heatmap = heatmap
        
        stmt = insert(PostActivityHeatmap).values(
            user_id=self.user.id,
            heatmap_data={"data": normalized_heatmap},
        ).on_conflict_do_update(
            index_elements=['user_id'],
            set_={
                "heatmap_data": {"data": normalized_heatmap},
                "last_updated_at": datetime.datetime.utcnow()
            }
        )
        await self.db.execute(stmt)
        await self.db.commit()
        log.info("heatmap.generated", user_id=self.user.id)

# --- backend/app\services\automation_service.py ---

# backend/app/services/automation_service.py
import datetime
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.services.vk_api import VKAccessDeniedError
from app.db.models import SentCongratulation
from app.api.schemas.actions import BirthdayCongratulationRequest

class AutomationService(BaseVKService):

    async def congratulate_friends_with_birthday(self, params: BirthdayCongratulationRequest):
        return await self._execute_logic(self._congratulate_friends_logic, params)

    async def _congratulate_friends_logic(self, params: BirthdayCongratulationRequest):
        await self.emitter.send_log("Запуск задачи: Поздравление друзей с Днем Рождения.", "info")
        
        friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="bdate,sex")
        if not friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return

        today = datetime.date.today()
        today_str = f"{today.day}.{today.month}"
        
        birthday_friends = [f for f in friends if f.get("bdate") and f.get("bdate").startswith(today_str)]

        if not birthday_friends:
            await self.emitter.send_log("Сегодня нет дней рождения у друзей.", "info")
            return

        await self.emitter.send_log(f"Найдено именинников: {len(birthday_friends)} чел. Начинаем поздравлять.", "info")

        current_year = today.year
        stmt = select(SentCongratulation.friend_vk_id).where(
            and_(SentCongratulation.user_id == self.user.id, SentCongratulation.year == current_year)
        )
        already_congratulated_ids = {row[0] for row in (await self.db.execute(stmt)).all()}

        processed_count = 0
        for friend in birthday_friends:
            friend_id = friend['id']
            if friend_id in already_congratulated_ids:
                continue

            name = friend.get("first_name", "")
            sex = friend.get("sex")

            template = params.message_template_default
            if sex == 2 and params.message_template_male:
                template = params.message_template_male
            elif sex == 1 and params.message_template_female:
                template = params.message_template_female

            message = template.replace("{name}", name)
            url = f"https://vk.com/id{friend_id}"

            await self.humanizer.imitate_simple_action()

            try:
                if await self.vk_api.send_message(friend_id, message):
                    insert_stmt = insert(SentCongratulation).values(
                        user_id=self.user.id, friend_vk_id=friend_id, year=current_year
                    ).on_conflict_do_nothing()
                    await self.db.execute(insert_stmt)
                    
                    await self.emitter.send_log(f"Успешно отправлено поздравление для {name}", "success", target_url=url)
                    processed_count += 1
                else:
                    await self.emitter.send_log(f"Не удалось отправить поздравление для {name}.", "error", target_url=url)
            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить сообщение для {name} (профиль закрыт или ЧС).", "warning", target_url=url)
        
        await self.emitter.send_log(f"Задача завершена. Отправлено поздравлений: {processed_count}.", "success")
        
    async def set_online_status(self):
        return await self._execute_logic(self._set_online_status_logic)

    async def _set_online_status_logic(self):
        await self.emitter.send_log("Поддержание статуса 'онлайн'...", "debug")
        await self.vk_api.set_online()
        await self.emitter.send_log("Статус 'онлайн' успешно обновлен.", "success")

# --- backend/app\services\base.py ---

# backend/app/services/base.py
import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, DailyStats
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
        # Теперь мы предполагаем, что user.proxies всегда загружены
        working_proxies = [p for p in self.user.proxies if p.is_working]
        if not working_proxies:
            return None
        
        chosen_proxy = random.choice(working_proxies)
        return decrypt_data(chosen_proxy.encrypted_proxy_url)

    async def _get_today_stats(self) -> DailyStats:
        return await self.stats_repo.get_or_create_today_stats(self.user.id)

    async def _increment_stat(self, stats: DailyStats, field_name: str, value: int = 1):
        current_value = getattr(stats, field_name, 0)
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
            await self.emitter.send_log(f"Произошла критическая ошибка: {type(e).__name__} - {e}. Все изменения отменены.", status="error")
            raise

# --- backend/app\services\event_emitter.py ---

# backend/app/services/event_emitter.py
import datetime
import json
from datetime import UTC 
import structlog
from typing import Literal, Dict, Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Notification

LogLevel = Literal["debug", "info", "success", "warning", "error"]

class RedisEventEmitter:
    # ... (весь код этого класса остается без изменений) ...
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
            # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
            "timestamp": datetime.datetime.now(UTC).isoformat(),
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
            "task_history_id": self.task_history_id, "status": status, "result": result,
            "task_name": task_name, "created_at": created_at.isoformat() if created_at else None
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "task_history_update", "payload": payload})

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        new_notification = Notification(user_id=self.user_id, message=message, level=level)
        db.add(new_notification)
        await db.flush()
        await db.refresh(new_notification)
        payload = { "id": new_notification.id, "message": new_notification.message, "level": new_notification.level,
                    "is_read": new_notification.is_read, "created_at": new_notification.created_at.isoformat() }
        await self._publish(f"ws:user:{self.user_id}", {"type": "new_notification", "payload": payload})

# --- ДОБАВЬТЕ ЭТОТ КЛАСС В КОНЕЦ ФАЙЛА ---
class SystemLogEmitter:
    """
    Эмиттер-заглушка для фоновых задач (cron), который выводит логи в structlog,
    а не отправляет их пользователю через Redis.
    """
    def __init__(self, task_name: str, user_id: int | None = None):
        self.log = structlog.get_logger(task_name)
        if user_id:
            # Привязываем ID пользователя к логам для удобства отладки
            self.log = self.log.bind(user_id=user_id)

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        # Преобразуем статусы в уровни логирования structlog
        if status in ['error', 'warning']:
            # Используем соответствующий уровень для ошибок и предупреждений
            getattr(self.log, status)(message, url=target_url)
        else:
            # Все остальное (info, success, debug) логируем как info
            self.log.info(message, url=target_url, status=status)

    async def send_stats_update(self, stats_dict: Dict[str, Any]):
        # Обновления статистики для UI не нужны в фоновых задачах, просто игнорируем
        pass

    async def send_task_status_update(self, *args, **kwargs):
        # Обновления статуса задачи для UI не нужны, игнорируем
        pass

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        # Системные уведомления от фоновых задач также создаем в БД
        if self.user_id:
             new_notification = Notification(user_id=self.user_id, message=message, level=level)
             db.add(new_notification)
             # коммит будет выполнен в вызывающей функции

# --- backend/app\services\feed_service.py ---

# --- backend/app/services/feed_service.py ---
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.core.exceptions import UserLimitReachedError
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import LikeFeedRequest

class FeedService(BaseVKService):

    async def like_newsfeed(self, params: LikeFeedRequest):
        return await self._execute_logic(self._like_newsfeed_logic, params)

    async def _like_newsfeed_logic(self, params: LikeFeedRequest):
        await self.emitter.send_log(f"Запуск задачи: поставить {params.count} лайков в ленте новостей.", "info")
        stats = await self._get_today_stats()
        
        newsfeed_filter = "photo" if params.filters.only_with_photo else "post"

        await self.humanizer.imitate_page_view()
        response = await self.vk_api.get_newsfeed(count=params.count * 2, filters=newsfeed_filter)

        if not response or not response.get('items'):
            await self.emitter.send_log("Посты в ленте не найдены.", "warning")
            return

        posts = [p for p in response.get('items', []) if p.get('type') in ['post', 'photo']]
        author_ids = [abs(p['source_id']) for p in posts if p.get('source_id', 0) > 0]
        
        filtered_author_ids = set(author_ids)
        if author_ids:
            author_profiles = await self._get_user_profiles(list(set(author_ids)))
            filtered_authors = apply_filters_to_profiles(author_profiles, params.filters)
            filtered_author_ids = {a.get('id') for a in filtered_authors}

        processed_count = 0
        for item in posts:
            if processed_count >= params.count:
                break
            if stats.likes_count >= self.user.daily_likes_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит лайков ({self.user.daily_likes_limit}).")

            owner_id = item.get('source_id')
            item_id = item.get('post_id') or item.get('id')
            item_type = item.get('type')
            
            if not all([owner_id, item_id, item_type]) or item.get('likes', {}).get('user_likes') == 1:
                continue
                
            if owner_id > 0 and owner_id not in filtered_author_ids:
                continue

            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.add_like(item_type, owner_id, item_id)
            
            if result and 'likes' in result:
                processed_count += 1
                await self._increment_stat(stats, 'likes_count')
                if processed_count % 10 == 0:
                    await self.emitter.send_log(f"Поставлено лайков: {processed_count}/{params.count}", "info")
            else:
                url = f"https://vk.com/wall{owner_id}_{item_id}"
                await self.emitter.send_log(f"Не удалось поставить лайк. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков: {processed_count}.", "success")
        
    async def _get_user_profiles(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        if not user_ids: return []
        
        all_profiles = []
        for i in range(0, len(user_ids), 1000):
            chunk = user_ids[i:i + 1000]
            ids_str = ",".join(map(str, chunk))
            profiles = await self.vk_api.get_user_info(user_ids=ids_str)
            if profiles:
                all_profiles.extend(profiles)
        return all_profiles

# --- backend/app\services\friend_management_service.py ---

# backend/app/services/friend_management_service.py
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import RemoveFriendsRequest

class FriendManagementService(BaseVKService):

    async def remove_friends_by_criteria(self, params: RemoveFriendsRequest):
        return await self._execute_logic(self._remove_friends_by_criteria_logic, params)

    async def _remove_friends_by_criteria_logic(self, params: RemoveFriendsRequest):
        await self.emitter.send_log(f"Начинаем чистку друзей. Цель: удалить до {params.count} чел.", "info")
        stats = await self._get_today_stats()

        all_friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,is_closed,deactivated")
        if not all_friends:
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return

        banned_friends = []
        if params.filters.remove_banned:
            banned_friends = [f for f in all_friends if f.get('deactivated') in ['banned', 'deleted']]
        
        active_friends = [f for f in all_friends if not f.get('deactivated')]
        
        await self.emitter.send_log(f"Найдено забаненных/удаленных друзей: {len(banned_friends)}.", "info")
        
        # Используем централизованную функцию фильтрации со строго типизированными фильтрами
        filtered_active_friends = apply_filters_to_profiles(active_friends, params.filters)
        await self.emitter.send_log(f"Найдено друзей по критериям неактивности/пола: {len(filtered_active_friends)}.", "info")
        
        friends_to_remove = (banned_friends + filtered_active_friends)[:params.count]
        if not friends_to_remove:
            await self.emitter.send_log("Друзей для удаления по заданным критериям не найдено.", "success")
            return

        await self.emitter.send_log(f"Всего к удалению: {len(friends_to_remove)} чел. Начинаем процесс...", "info")
        processed_count = 0
        
        batch_size = 25
        for i in range(0, len(friends_to_remove), batch_size):
            batch = friends_to_remove[i:i + batch_size]
            
            calls = [{"method": "friends.delete", "params": {"user_id": friend.get('id')}} for friend in batch]
            
            await self.humanizer.imitate_simple_action()
            results = await self.vk_api.execute(calls)
            
            if results is None:
                await self.emitter.send_log(f"Пакетный запрос на удаление не удался.", "error")
                continue

            for friend, result in zip(batch, results):
                user_id = friend.get('id')
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"

                if isinstance(result, dict) and result.get('success') == 1:
                    processed_count += 1
                    await self._increment_stat(stats, 'friends_removed_count')
                    reason = f"({friend.get('deactivated', 'неактивность')})"
                    await self.emitter.send_log(f"Удален друг: {name} {reason}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', 'неизвестная ошибка') if isinstance(result, dict) else 'неизвестная ошибка'
                    await self.emitter.send_log(f"Не удалось удалить друга {name}. Причина: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Чистка завершена. Удалено друзей: {processed_count}.", "success")

# --- backend/app\services\group_management_service.py ---

# --- backend/app/services/group_management_service.py ---
from app.services.base import BaseVKService
from app.api.schemas.actions import LeaveGroupsRequest, JoinGroupsRequest

class GroupManagementService(BaseVKService):

    async def leave_groups_by_criteria(self, params: LeaveGroupsRequest):
        return await self._execute_logic(self._leave_groups_logic, params)

    async def _leave_groups_logic(self, params: LeaveGroupsRequest):
        await self.emitter.send_log(f"Запуск задачи: отписаться от {params.count} сообществ.", "info")

        response = await self.vk_api.get_groups(user_id=self.user.vk_id)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не удалось получить список сообществ или вы не состоите в группах.", "warning")
            return
        
        all_groups = [g for g in response['items'] if g.get('type') != 'event']
        
        groups_to_leave = all_groups
        keyword = (params.filters.status_keyword or "").lower().strip()

        if keyword:
            groups_to_leave = [group for group in all_groups if keyword in group.get('name', '').lower()]
            await self.emitter.send_log(f"Найдено {len(groups_to_leave)} сообществ по ключевому слову '{keyword}'.", "info")
        
        if not groups_to_leave:
            await self.emitter.send_log("Сообществ для отписки по заданным критериям не найдено.", "success")
            return

        groups_to_leave = groups_to_leave[:params.count]
        
        processed_count = 0
        for group in groups_to_leave:
            group_id = group['id']
            group_name = group['name']
            url = f"https://vk.com/public{group_id}"
            
            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.leave_group(group_id)

            if result == 1:
                processed_count += 1
                await self.emitter.send_log(f"Вы успешно покинули сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось покинуть сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Покинуто сообществ: {processed_count}.", "success")

    async def join_groups_by_criteria(self, params: JoinGroupsRequest):
        return await self._execute_logic(self._join_groups_logic, params)

    async def _join_groups_logic(self, params: JoinGroupsRequest):
        keyword = (params.filters.status_keyword or "").strip()
        if not keyword:
            await self.emitter.send_log("Не указано ключевое слово для поиска групп.", "error")
            return

        await self.emitter.send_log(f"Запуск задачи: вступить в {params.count} сообществ по запросу '{keyword}'.", "info")

        response = await self.vk_api.search_groups(query=keyword, count=params.count * 2)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не найдено сообществ по вашему запросу.", "warning")
            return

        user_groups_response = await self.vk_api.get_groups(user_id=self.user.vk_id, extended=0)
        user_group_ids = set(user_groups_response.get('items', []) if user_groups_response else [])

        groups_to_join = [
            g for g in response['items'] 
            if g['id'] not in user_group_ids and g.get('is_closed', 1) == 0
        ][:params.count]

        if not groups_to_join:
            await self.emitter.send_log("Новых открытых сообществ для вступления не найдено.", "success")
            return
        
        processed_count = 0
        for group in groups_to_join:
            group_id = group['id']
            group_name = group['name']
            url = f"https://vk.com/public{group_id}"

            await self.humanizer.imitate_simple_action()
            result = await self.vk_api.join_group(group_id)

            if result == 1:
                processed_count += 1
                await self.emitter.send_log(f"Успешное вступление в сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось вступить в сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Вступлений в сообщества: {processed_count}.", "success")

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
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AcceptFriendsRequest

class IncomingRequestService(BaseVKService):
    async def accept_friend_requests(self, params: AcceptFriendsRequest):
        return await self._execute_logic(self._accept_friend_requests_logic, params)

    async def _accept_friend_requests_logic(self, params: AcceptFriendsRequest):
        await self.emitter.send_log("Начинаем прием заявок в друзья...", "info")
        stats = await self._get_today_stats()
        
        response = await self.vk_api.get_incoming_friend_requests(extended=1)
        if not response or not response.get('items'):
            await self.emitter.send_log("Входящие заявки не найдены.", "info")
            return
        
        profiles = response.get('items', [])
        await self.emitter.send_log(f"Найдено {len(profiles)} заявок. Начинаем фильтрацию...", "info")
        
        filtered_profiles = apply_filters_to_profiles(profiles, params.filters)

        await self.emitter.send_log(f"После фильтрации осталось: {len(filtered_profiles)}.", "info")
        
        if not filtered_profiles:
            await self.emitter.send_log("Подходящих заявок для приема не найдено.", "success")
            return
        
        processed_count = 0
        batch_size = 25
        for i in range(0, len(filtered_profiles), batch_size):
            batch = filtered_profiles[i:i + batch_size]
            
            calls = [{"method": "friends.add", "params": {"user_id": p.get('id')}} for p in batch]

            await self.humanizer.imitate_simple_action()
            results = await self.vk_api.execute(calls)

            if results is None:
                await self.emitter.send_log("Пакетный запрос на принятие заявок не удался.", "error")
                continue

            for profile, result in zip(batch, results):
                user_id = profile.get('id')
                name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"
                
                if result in [1, 2, 4]:  # Коды успешного добавления от VK API
                    processed_count += 1
                    await self._increment_stat(stats, 'friend_requests_accepted_count')
                    await self.emitter.send_log(f"Принята заявка от {name}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', f'неизвестная ошибка, код {result}') if isinstance(result, dict) else f'код {result}'
                    await self.emitter.send_log(f"Не удалось принять заявку от {name}. Ответ VK: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Завершено. Принято заявок: {processed_count}.", "success")

# --- backend/app\services\message_service.py ---

# backend/app/services/message_service.py
import random
from app.services.base import BaseVKService
from app.core.exceptions import InvalidActionSettingsError
from app.services.vk_api import VKAccessDeniedError
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import MassMessagingRequest

class MessageService(BaseVKService):

    async def send_mass_message(self, params: MassMessagingRequest):
        return await self._execute_logic(self._send_mass_message_logic, params)

    async def _send_mass_message_logic(self, params: MassMessagingRequest):
        if not params.message_text or not params.message_text.strip():
            raise InvalidActionSettingsError("Текст сообщения не может быть пустым.")

        await self.emitter.send_log(f"Запуск массовой рассылки. Цель: {params.count} сообщений.", "info")
        stats = await self._get_today_stats()

        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,status")
        if not friends_response:
            await self.emitter.send_log("Не удалось получить список друзей.", "error")
            return

        filtered_friends = apply_filters_to_profiles(friends_response, params.filters)
        if not filtered_friends:
            await self.emitter.send_log("После применения фильтров не осталось друзей для рассылки.", "warning")
            return

        await self.emitter.send_log(f"Найдено друзей по фильтрам: {len(filtered_friends)}. Начинаем обработку.", "info")
        random.shuffle(filtered_friends)
        
        target_friends = filtered_friends
        if params.only_new_dialogs:
            dialogs = await self.vk_api.get_conversations(count=200)
            dialog_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in dialogs.get('items', [])}
            target_friends = [f for f in filtered_friends if f.get('id') not in dialog_peer_ids]
            await self.emitter.send_log(f"Режим 'Только новые диалоги'. Осталось целей: {len(target_friends)}.", "info")
        
        if not target_friends:
            await self.emitter.send_log("Не найдено подходящих получателей.", "success")
            return
            
        processed_count = 0
        for friend in target_friends:
            if processed_count >= params.count:
                break

            friend_id = friend.get('id')
            name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
            url = f"https://vk.com/id{friend_id}"
            
            final_message = params.message_text.replace("{name}", friend.get('first_name', ''))

            await self.humanizer.imitate_page_view()

            try:
                if await self.vk_api.send_message(friend_id, final_message):
                    processed_count += 1
                    await self._increment_stat(stats, 'messages_sent_count')
                    await self.emitter.send_log(f"Сообщение для {name} успешно отправлено.", "success", target_url=url)
                else:
                    await self.emitter.send_log(f"Не удалось отправить сообщение для {name}.", "error", target_url=url)
            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить сообщение (профиль закрыт или ЧС): {name}", "warning", target_url=url)
            except Exception as e:
                await self.emitter.send_log(f"Ошибка при отправке сообщения для {name}: {e}", "error", target_url=url)

        await self.emitter.send_log(f"Рассылка завершена. Отправлено сообщений: {processed_count}.", "success")

# --- backend/app\services\outgoing_request_service.py ---

# backend/app/services/outgoing_request_service.py
from typing import Dict, Any
from app.services.base import BaseVKService
from app.db.models import DailyStats, FriendRequestLog
from sqlalchemy.dialects.postgresql import insert
from app.core.exceptions import UserLimitReachedError
from app.core.config import settings
from redis.asyncio import Redis as AsyncRedis
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AddFriendsRequest

redis_lock_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)

class OutgoingRequestService(BaseVKService):
    async def add_recommended_friends(self, params: AddFriendsRequest):
        return await self._execute_logic(self._add_recommended_friends_logic, params)

    async def _add_recommended_friends_logic(self, params: AddFriendsRequest):
        await self.emitter.send_log(f"Начинаем добавление {params.count} друзей из рекомендаций...", "info")
        stats = await self._get_today_stats()
        
        response = await self.vk_api.get_recommended_friends(count=params.count * 3)
        if not response or not response.get('items'):
            await self.emitter.send_log("Рекомендации не найдены.", "warning")
            return

        filtered_profiles = apply_filters_to_profiles(response.get('items', []), params.filters)
        await self.emitter.send_log(f"Найдено {len(response.get('items', []))} рекомендаций. После фильтрации осталось: {len(filtered_profiles)}.", "info")
        
        processed_count = 0
        for profile in filtered_profiles:
            if processed_count >= params.count: break
            if stats.friends_added_count >= self.user.daily_add_friends_limit:
                raise UserLimitReachedError(f"Достигнут дневной лимит на отправку заявок ({self.user.daily_add_friends_limit}).")
            
            user_id = profile.get('id')
            if not user_id: continue
            
            lock_key = f"lock:add_friend:{self.user.id}:{user_id}"
            if not await redis_lock_client.set(lock_key, "1", ex=3600, nx=True):
                continue

            await self.humanizer.imitate_page_view()
            
            message = params.message_text.replace("{name}", profile.get("first_name", "")) if params.message_text and params.send_message_on_add else None
            result = await self.vk_api.add_friend(user_id, message) 
            
            name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
            url = f"https://vk.com/id{user_id}"
            
            if result in [1, 2, 4]:
                processed_count += 1
                await self._increment_stat(stats, 'friends_added_count')
                
                log_stmt = insert(FriendRequestLog).values(user_id=self.user.id, target_vk_id=user_id).on_conflict_do_nothing()
                await self.db.execute(log_stmt)

                log_msg = f"Отправлена заявка пользователю {name}"
                if params.send_message_on_add and params.message_text:
                    log_msg += " с сообщением."
                await self.emitter.send_log(log_msg, "success", target_url=url)
                
                if params.like_config.enabled and not profile.get('is_closed', True):
                    await self._like_user_content(user_id, profile, params.like_config, stats)
            else:
                await self.emitter.send_log(f"Не удалось отправить заявку {name}. Ответ VK: {result}", "error", target_url=url)
                await redis_lock_client.delete(lock_key)

        await self.emitter.send_log(f"Завершено. Отправлено заявок: {processed_count}.", "success")

    async def _like_user_content(self, user_id: int, profile: Dict[str, Any], config: Dict[str, Any], stats: DailyStats):
        if stats.likes_count >= self.user.daily_likes_limit:
            await self.emitter.send_log("Достигнут дневной лимит лайков, пропуск лайкинга после добавления.", "warning")
            return

        targets = config.targets
        
        if 'avatar' in targets and profile.get('photo_id'):
            photo_id_parts = profile.get('photo_id', '').split('_')
            if len(photo_id_parts) == 2:
                photo_id = int(photo_id_parts[1])
                await self.humanizer.imitate_simple_action()
                if await self.vk_api.add_like('photo', user_id, photo_id):
                    await self._increment_stat(stats, 'likes_count')
                    await self.emitter.send_log(f"Поставлен лайк на аватар.", "success", target_url=f"https://vk.com/photo{user_id}_{photo_id}")

        if 'wall' in targets:
            wall = await self.vk_api.get_wall(owner_id=user_id, count=1)
            if wall and wall.get('items'):
                post = wall['items'][0]
                if stats.likes_count < self.user.daily_likes_limit:
                    await self.humanizer.imitate_simple_action()
                    if await self.vk_api.add_like('post', user_id, post.get('id')):
                        await self._increment_stat(stats, 'likes_count')
                        await self.emitter.send_log(f"Поставлен лайк на пост на стене.", "success", target_url=f"https://vk.com/wall{user_id}_{post.get('id')}")

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

# --- backend/app\services\scenario_service.py ---

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

# --- backend/app\services\story_service.py ---

# backend/app/services/story_service.py
from app.services.base import BaseVKService
from app.api.schemas.actions import EmptyRequest

class StoryService(BaseVKService):

    async def view_stories(self, params: EmptyRequest):
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
import asyncio
from typing import Optional, Dict, Any, List
from app.core.config import settings

class VKAPIError(Exception):
    def __init__(self, message: str, error_code: int):
        self.message = message
        self.error_code = error_code
        super().__init__(f"VK API Error [{self.error_code}]: {self.message}")

class VKRateLimitError(VKAPIError): pass
class VKFloodControlError(VKAPIError): pass # Ошибка 9 - Flood control
class VKInvalidTokenError(VKAPIError): pass
class VKAccessDeniedError(VKAPIError): pass
class VKAuthError(VKAPIError): pass

class VKAPI:
    def __init__(self, access_token: str, proxy: Optional[str] = None):
        self.access_token = access_token
        self.proxy = proxy
        self.api_version = settings.VK_API_VERSION
        self.base_url = "https://api.vk.com/method/"
        self.user_id = None

    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if params is None:
            params = {}
        
        params['access_token'] = self.access_token
        params['v'] = self.api_version

        async with aiohttp.ClientSession() as session:
            try:
                # Цикл повторных попыток для обхода временных лимитов
                for attempt in range(3):
                    async with session.post(f"{self.base_url}{method}", data=params, proxy=self.proxy, timeout=20) as response:
                        data = await response.json()
                        
                        if 'error' in data:
                            error_data = data['error']
                            error_code = error_data.get('error_code')
                            error_msg = error_data.get('error_msg', 'Unknown VK error')
                            
                            # Если это Flood Control или Rate Limit, ждем и пробуем снова
                            if error_code == 6 or error_code == 9:
                                wait_time = 1 + attempt
                                print(f"  [API-WARN] Сработал Flood/Rate Control (ошибка {error_code}). Пауза {wait_time} сек. Попытка {attempt + 2}/3...")
                                await asyncio.sleep(wait_time)
                                continue # Переходим к следующей итерации цикла
                            
                            # Для других ошибок - сразу выходим
                            if error_code == 5: raise VKAuthError(error_msg, error_code)
                            elif error_code in [15, 18, 203, 902]: raise VKAccessDeniedError(error_msg, error_code)
                            else: raise VKAPIError(error_msg, error_code)

                        # Если ошибки нет, возвращаем результат
                        return data.get('response')
                
                # Если все попытки провалились
                raise VKAPIError("Превышено количество попыток после ошибок Flood/Rate Control", 9)

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
        # Обратите внимание: users.get МОЖЕТ возвращать counters для ОДНОГО пользователя, но не для списка друзей.
        # Эта логика остается, так как она полезна для точечных проверок (например, при приеме заявок).
        if response and isinstance(response, list):
            return response[0] if user_ids is None and len(response) == 1 else response
        return None
    
    async def get_user_friends(self, user_id: int, fields: str = "sex,bdate,city,online,last_seen,is_closed,deactivated") -> Optional[List[Dict[str, Any]]]:
        params = {"user_id": user_id, "fields": fields, "order": "random"}
        response = await self._make_request("friends.get", params=params)
        
        if not response or "items" not in response:
            return None
            
        items = response["items"]
        # Если VK вернул просто список ID, преобразуем его в стандартный формат
        if fields == "" and isinstance(items, list) and all(isinstance(x, int) for x in items):
            return [{"id": user_id} for user_id in items]
        
        return items

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
        params = {"count": count, **kwargs}
        if 'extended' in params and params['extended'] == 1:
            params['fields'] = "sex,online,last_seen,is_closed,status,counters"
        return await self._make_request("friends.getRequests", params=params)

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
    
    async def get_groups(self, user_id: int, extended: int = 1, fields: str = "members_count", count: int = 1000) -> Optional[Dict[str, Any]]:
        return await self._make_request("groups.get", params={"user_id": user_id, "extended": extended, "fields": fields, "count": count})

    async def leave_group(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.leave", params={"group_id": group_id})

    async def search_groups(self, query: str, count: int = 100, sort: int = 6) -> Optional[Dict[str, Any]]:
        return await self._make_request("groups.search", params={"q": query, "count": count, "sort": sort})
    
    async def join_group(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.join", params={"group_id": group_id})

async def is_token_valid(vk_token: str) -> Optional[int]:
    vk_api = VKAPI(access_token=vk_token)
    try:
        user_info = await vk_api.get_user_info()
        return user_info.get('id') if user_info else None
    except VKAPIError:
        return None

# --- backend/app\services\vk_user_filter.py ---

# backend/app/services/vk_user_filter.py
import datetime
from typing import Dict, Any, List, Optional
from app.api.schemas.actions import ActionFilters
from app.services.vk_api import VKAPI

async def apply_filters_to_profiles(
    profiles: List[Dict[str, Any]],
    filters: ActionFilters,
    vk_api: Optional[VKAPI] = None  # Параметр vk_api оставлен для совместимости, но не используется
) -> List[Dict[str, Any]]:
    """
    Применяет "быстрые" фильтры (пол, город и т.д.) на основе уже имеющихся данных.
    Фильтрация по счетчикам (друзья/подписчики) здесь не производится.
    """
    filtered_profiles = []
    now_ts = datetime.datetime.now().timestamp()

    for profile in profiles:
        # Пропускаем "собачек", если это не задача на удаление
        if not filters.remove_banned and profile.get('deactivated'):
            continue
        
        # Фильтр по закрытому профилю
        if not filters.allow_closed_profiles and profile.get('is_closed', True):
            continue
        
        # Простые фильтры
        if filters.sex and profile.get('sex') != filters.sex: continue
        if filters.is_online and not profile.get('online', 0): continue
        
        last_seen_ts = profile.get('last_seen', {}).get('time', 0)
        if filters.last_seen_hours and (not last_seen_ts or (now_ts - last_seen_ts) > (filters.last_seen_hours * 3600)): continue
        if filters.last_seen_days and (not last_seen_ts or (now_ts - last_seen_ts) > (filters.last_seen_days * 86400)): continue
        
        status_keyword = (filters.status_keyword or "").lower().strip()
        if status_keyword and status_keyword not in profile.get('status', '').lower(): continue
        
        city_filter = (filters.city or "").lower().strip()
        if city_filter and city_filter not in profile.get('city', {}).get('title', '').lower(): continue
        
        filtered_profiles.append(profile)

    return filtered_profiles

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



# --- backend/app\tasks\cron.py ---

# --- backend/app/tasks/cron.py ---
import datetime
import structlog
import pytz
from redis.asyncio import Redis
from sqlalchemy import func, select, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import AsyncSessionFactory
from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, Automation, TaskHistory, User, Notification, FriendRequestLog, FriendRequestStatus
)
from app.services.event_emitter import SystemLogEmitter
from app.services.vk_api import VKAPI, VKAuthError
from app.core.security import decrypt_data
from app.services.analytics_service import AnalyticsService
from app.core.config_loader import PLAN_CONFIG, AUTOMATIONS_CONFIG
from app.core.plans import get_limits_for_plan

log = structlog.get_logger(__name__)

# Эта карта нужна здесь для _run_daily_automations_async
TASK_FUNC_MAP_ARQ = {
    "accept_friends": "accept_friend_requests_task",
    "like_feed": "like_feed_task",
    "add_recommended": "add_recommended_friends_task",
    "view_stories": "view_stories_task",
    "remove_friends": "remove_friends_by_criteria_task",
    "mass_messaging": "mass_messaging_task",
    "join_groups": "join_groups_by_criteria_task",
    "leave_groups": "leave_groups_by_criteria_task",
    "birthday_congratulation": "birthday_congratulation_task",
    "eternal_online": "eternal_online_task",
}

async def _create_and_run_arq_task(session, arq_pool, user_id, task_name_key, settings_dict):
    task_func_name = TASK_FUNC_MAP_ARQ.get(task_name_key)
    if not task_func_name:
        log.warn("cron.arq_task_not_found", task_name=task_name_key)
        return

    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_name_key), None)
    display_name = task_config.name if task_config else "Автоматическая задача"

    task_history = TaskHistory(
        user_id=user_id, task_name=display_name, status="PENDING", parameters=settings_dict
    )
    session.add(task_history)
    await session.flush()

    job = await arq_pool.enqueue_job(
        task_func_name, task_history_id=task_history.id, **(settings_dict or {})
    )
    task_history.celery_task_id = job.job_id
    await session.commit()


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
    from app.worker import redis_settings # Локальный импорт для избежания цикла
    from arq.connections import create_pool

    redis_lock_client = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=2, decode_responses=True)
    lock_key = f"lock:task:run_automations:{automation_group}"

    if not await redis_lock_client.set(lock_key, "1", ex=240, nx=True):
        log.warn("run_daily_automations.already_running", group=automation_group)
        await redis_lock_client.close()
        return

    arq_pool = await create_pool(redis_settings)
    try:
        async with AsyncSessionFactory() as session:
            # ... остальная логика без изменений, но использующая _create_and_run_arq_task
            now_utc = datetime.datetime.now(pytz.utc)
            moscow_tz = pytz.timezone("Europe/Moscow")
            now_moscow = now_utc.astimezone(moscow_tz)

            automation_ids_in_group = [item.id for item in AUTOMATIONS_CONFIG if item.group == automation_group]
            if not automation_ids_in_group:
                log.warn("run_daily_automations.unknown_group", group=automation_group)
                return

            active_automations_stmt = (
                select(Automation)
                .join(User)
                .where(
                    Automation.is_active == True,
                    Automation.automation_type.in_(automation_ids_in_group),
                    or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
                )
                .options(selectinload(Automation.user))
            )
            result = await session.execute(active_automations_stmt)
            active_automations = result.scalars().unique().all()
            
            log.info("run_daily_automations.start", count=len(active_automations), group=automation_group)

            for automation in active_automations:
                # ... (проверки расписания для eternal_online) ...
                automation.last_run_at = now_utc
                await _create_and_run_arq_task(session, arq_pool, automation.user_id, automation.automation_type, automation.settings)

    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()
        await arq_pool.close()

async def _check_expired_plans_async():
    # ... (логика без изменений)
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.now(pytz.utc)
        stmt = select(User).where(
            User.plan != 'Expired', User.plan_expires_at != None, User.plan_expires_at < now
        )
        expired_users = (await session.execute(stmt)).scalars().all()
        if not expired_users: return
        log.info("plans.expired_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan("Expired")
        user_ids_to_deactivate = [user.id for user in expired_users]
        notifications_to_add = [Notification(user_id=user.id, message=f"Срок действия тарифа '{user.plan}' истек.", level="error") for user in expired_users]
        session.add_all(notifications_to_add)
        await session.execute(update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False))
        await session.execute(update(User).where(User.id.in_(user_ids_to_deactivate)).values(
            plan="Expired",
            daily_likes_limit=expired_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=expired_plan_limits["daily_add_friends_limit"]
        ))
        await session.commit()

async def _update_friend_request_statuses_async():
    # ... (логика без изменений)
    async with AsyncSessionFactory() as session:
        stmt = select(User).where(User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending))
        users_with_pending = (await session.execute(stmt)).scalars().unique().all()
        if not users_with_pending: return
        log.info("conversion_tracker.start", users_count=len(users_with_pending))
        for user in users_with_pending:
            try:
                vk_token = decrypt_data(user.encrypted_vk_token)
                if not vk_token: continue
                vk_api = VKAPI(access_token=vk_token)
                pending_reqs = (await session.execute(select(FriendRequestLog).where(
                    FriendRequestLog.user_id == user.id, FriendRequestLog.status == FriendRequestStatus.pending
                ))).scalars().all()
                friends_response = await vk_api.get_user_friends(user_id=user.vk_id)
                if friends_response is None: continue
                friend_ids = {f['id'] for f in friends_response}
                accepted_req_ids = [req.id for req in pending_reqs if req.target_vk_id in friend_ids]
                if accepted_req_ids:
                    await session.execute(update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                        status=FriendRequestStatus.accepted, resolved_at=datetime.datetime.now(pytz.utc)
                    ))
                    log.info("conversion_tracker.updated", user_id=user.id, count=len(accepted_req_ids))
            except VKAuthError: log.warn("conversion_tracker.auth_error", user_id=user.id)
            except Exception as e: log.error("conversion_tracker.user_error", user_id=user.id, error=str(e))
        await session.commit()

async def _generate_all_heatmaps_async():
    async with AsyncSessionFactory() as session:
        now = datetime.datetime.utcnow()
        stmt = select(User).where(
            User.plan.in_(['Plus', 'PRO', 'Agency']),
            or_(User.plan_expires_at.is_(None), User.plan_expires_at > now)
        )
        users = (await session.execute(stmt)).scalars().all()
        if not users:
            log.info("heatmap_generator.no_active_users")
            return

        log.info("heatmap_generator.start", users_count=len(users))
        for user in users:
            try:
                # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
                emitter = SystemLogEmitter(task_name="heatmap_generator", user_id=user.id)
                service = AnalyticsService(db=session, user=user, emitter=emitter)
                # -------------------------
                await service.generate_post_activity_heatmap()
            except Exception as e:
                log.error("heatmap_generator.user_error", user_id=user.id, error=str(e))

# --- backend/app\tasks\cron_jobs.py ---

# backend/app/tasks/cron_jobs.py
from app.tasks.cron import (
    _aggregate_daily_stats_async,
    _check_expired_plans_async,
    _generate_all_heatmaps_async,
    _update_friend_request_statuses_async,
    _run_daily_automations_async
)

async def aggregate_daily_stats_job(ctx):
    await _aggregate_daily_stats_async()

async def check_expired_plans_job(ctx):
    await _check_expired_plans_async()

async def generate_all_heatmaps_job(ctx):
    await _generate_all_heatmaps_async()

async def update_friend_request_statuses_job(ctx):
    await _update_friend_request_statuses_async()

# Эта задача заменит несколько старых задач Celery
async def run_standard_automations_job(ctx):
    await _run_daily_automations_async(automation_group='standard')

async def run_online_automations_job(ctx):
    await _run_daily_automations_async(automation_group='online')

# --- backend/app\tasks\maintenance.py ---

# backend/app/tasks/maintenance.py
import datetime
import structlog
from sqlalchemy import delete, select

# Импорты Celery удалены
from app.db.session import AsyncSessionFactory
from app.db.models import TaskHistory, User

log = structlog.get_logger(__name__)

async def _clear_old_task_history_async():
    async with AsyncSessionFactory() as session:
        # Удаляем записи старше 90 дней для платных тарифов
        pro_plus_cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=90)
        stmt_pro = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                select(User.id).filter(User.plan.in_(['PRO', 'Plus', 'Agency']))
            ),
            TaskHistory.created_at < pro_plus_cutoff
        )
        pro_result = await session.execute(stmt_pro)

        # Удаляем записи старше 30 дней для Базового и Истекшего
        base_cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        stmt_base = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                select(User.id).filter(User.plan.in_(['Базовый', 'Expired']))
            ),
            TaskHistory.created_at < base_cutoff
        )
        base_result = await session.execute(stmt_base)

        await session.commit()
        total_deleted = pro_result.rowcount + base_result.rowcount
        log.info("maintenance.task_history_cleaned", count=total_deleted)


# --- backend/app\tasks\maintenance_jobs.py ---

# backend/app/tasks/maintenance_jobs.py
from app.tasks.maintenance import _clear_old_task_history_async

async def clear_old_task_history_job(ctx):
    await _clear_old_task_history_async()

# --- backend/app\tasks\main_tasks.py ---

# backend/app/tasks/main_tasks.py
import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.db.models import User, TaskHistory, ScheduledPost, ScheduledPostStatus, Automation
from app.db.session import AsyncSessionFactory
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAPI, VKAuthError
from app.core.constants import TaskKey
from app.tasks.service_maps import TASK_CONFIG_MAP
from app.core.security import decrypt_data
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.services.scenario_service import ScenarioExecutionService

log = structlog.get_logger(__name__)


async def _execute_task_logic(ctx, task_history_id: int):
    """
    Универсальная функция для выполнения логики любой задачи.
    """
    async with AsyncSessionFactory() as session:
        # Шаг 1: "Жадно" загружаем все, что нам нужно.
        stmt = (
            select(TaskHistory)
            .where(TaskHistory.id == task_history_id)
            .options(
                selectinload(TaskHistory.user).selectinload(User.proxies)
            )
        )
        result = await session.execute(stmt)
        task_history = result.scalar_one_or_none()

        if not task_history or not task_history.user:
            log.error("task.logic.not_found", task_history_id=task_history_id)
            return

        # Шаг 2: Извлекаем все необходимые данные в локальные переменные.
        user_for_task = task_history.user
        current_task_name = task_history.task_name
        current_created_at = task_history.created_at
        task_parameters = task_history.parameters or {}

        # Шаг 3: Отсоединяем объект пользователя от сессии.
        session.expunge(user_for_task)

        redis_pool = ctx['redis_pool']
        emitter = RedisEventEmitter(redis_pool)
        emitter.set_context(user_for_task.id, task_history_id)
        
        try:
            # Шаг 4: Теперь можно безопасно коммитить изменение статуса.
            task_history.status = "STARTED"
            await session.commit()
            
            await emitter.send_task_status_update(status="STARTED", task_name=current_task_name, created_at=current_created_at)

            task_key_str = next((item.id for item in AUTOMATIONS_CONFIG if item.name == current_task_name), None)
            if not task_key_str:
                raise ValueError(f"Не удалось найти ключ задачи для имени '{current_task_name}'")

            ServiceClass, method_name, ParamsModel = TASK_CONFIG_MAP[TaskKey(task_key_str)]
            params = ParamsModel(**task_parameters)

            service_instance = ServiceClass(db=session, user=user_for_task, emitter=emitter)
            await getattr(service_instance, method_name)(params)

            task_history.status = "SUCCESS"
            task_history.result = "Задача успешно выполнена."

        except VKAuthError as e:
            task_history.status = "FAILURE"
            task_history.result = "Ошибка авторизации VK. Токен невалиден."
            log.error("task_runner.auth_error_critical", user_id=user_for_task.id, error=str(e))
            await emitter.send_system_notification(session, "Критическая ошибка: токен VK недействителен. Автоматизации остановлены.", "error")
            await session.execute(update(Automation).where(Automation.user_id == user_for_task.id).values(is_active=False))
        except UserActionException as e:
            task_history.status = "FAILURE"
            task_history.result = str(e)
            await emitter.send_system_notification(session, str(e), "error")
        except Exception as e:
            task_history.status = "FAILURE"
            task_history.result = f"Непредвиденная ошибка: {type(e).__name__}"
            log.exception("task_runner.unhandled_exception", id=task_history_id)
        
        finally:
            final_status = task_history.status
            final_result = task_history.result
            
            await session.merge(task_history)
            await session.commit()
            
            await emitter.send_task_status_update(status=final_status, result=final_result, task_name=current_task_name, created_at=current_created_at)


# --- Определяем все задачи, теперь они принимают `ctx` ---

async def like_feed_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def add_recommended_friends_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def accept_friend_requests_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def remove_friends_by_criteria_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def view_stories_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def birthday_congratulation_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def mass_messaging_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def eternal_online_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def leave_groups_by_criteria_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)

async def join_groups_by_criteria_task(ctx, task_history_id: int, **kwargs):
    await _execute_task_logic(ctx, task_history_id)


# --- Задачи со своей собственной логикой ---

async def publish_scheduled_post_task(ctx, post_id: int):
    async with AsyncSessionFactory() as session:
        post = await session.get(ScheduledPost, post_id)
        if not post or post.status != ScheduledPostStatus.scheduled:
            return

        user = await session.get(User, post.user_id)
        if not user:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Пользователь не найден"
            await session.commit()
            return

        vk_token = decrypt_data(user.encrypted_vk_token)
        if not vk_token:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Токен пользователя недействителен"
            await session.commit()
            return

        vk_api = VKAPI(access_token=vk_token)

        try:
            # wall.post не существует в vk_api.py, предполагаем, что это была опечатка и имелся в виду универсальный метод
            # или специальный метод для постов, которого нет в предоставленных файлах.
            # Для исправления используем базовый _make_request.
            result = await vk_api._make_request("wall.post", params={
                "owner_id": int(post.vk_profile_id),
                "message": post.post_text or "",
                "attachments": ",".join(post.attachments or [])
            })
            post.status = ScheduledPostStatus.published
            post.vk_post_id = str(result.get("post_id"))
        except VKAuthError as e:
            post.status = ScheduledPostStatus.failed
            post.error_message = f"Ошибка авторизации: {e.message}. Обновите токен."
        except Exception as e:
            post.status = ScheduledPostStatus.failed
            post.error_message = str(e)

        await session.commit()

async def run_scenario_from_scheduler_task(ctx, scenario_id: int, user_id: int):
    log.info("scenario.runner.start", scenario_id=scenario_id, user_id=user_id)
    try:
        async with AsyncSessionFactory() as session:
            executor = ScenarioExecutionService(session, scenario_id, user_id)
            await executor.run()
    except Exception as e:
        log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e), exc_info=True)
    finally:
        log.info("scenario.runner.finished", scenario_id=scenario_id)

# --- backend/app\tasks\profile_parser.py ---

# backend/app/tasks/profile_parser.py
import asyncio
import datetime
import structlog
from sqlalchemy import select, or_

# Импорты Celery удалены
from app.db.session import AsyncSessionFactory
from app.db.models import User
from app.services.profile_analytics_service import ProfileAnalyticsService
from app.services.vk_api import VKAuthError

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



# --- backend/app\tasks\profile_parser_jobs.py ---

# backend/app/tasks/profile_parser_jobs.py
from app.tasks.profile_parser import _snapshot_all_users_metrics_async

async def snapshot_all_users_metrics_job(ctx):
    await _snapshot_all_users_metrics_async()

# --- backend/app\tasks\service_maps.py ---

# backend/app/tasks/service_maps.py
# Этот файл разрывает циклическую зависимость между runner.py и scenario_service.py
# Он является центральным местом для сопоставления задач с их исполнителями (сервисами).

# Импортируем все необходимые сервисы и схемы
from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService
from app.core.constants import TaskKey
from app.api.schemas import actions as ActionSchemas

# Карта для исполнителя сценариев (Service, method_name)
TASK_SERVICE_MAP = {
    TaskKey.LIKE_FEED: (FeedService, "like_newsfeed"),
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "add_recommended_friends"),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "accept_friend_requests"),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "remove_friends_by_criteria"),
    TaskKey.VIEW_STORIES: (StoryService, "view_stories"),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "congratulate_friends_with_birthday"),
    TaskKey.MASS_MESSAGING: (MessageService, "send_mass_message"),
    TaskKey.ETERNAL_ONLINE: (AutomationService, "set_online_status"),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "leave_groups_by_criteria"),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "join_groups_by_criteria"),
}

# Полная карта для runner.py (Service, method_name, ParamsModel)
# Теперь она живет здесь, а не в runner.py
TASK_CONFIG_MAP = {
    TaskKey.LIKE_FEED: (FeedService, "like_newsfeed", ActionSchemas.LikeFeedRequest),
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "add_recommended_friends", ActionSchemas.AddFriendsRequest),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "accept_friend_requests", ActionSchemas.AcceptFriendsRequest),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "remove_friends_by_criteria", ActionSchemas.RemoveFriendsRequest),
    TaskKey.VIEW_STORIES: (StoryService, "view_stories", ActionSchemas.EmptyRequest),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "congratulate_friends_with_birthday", ActionSchemas.BirthdayCongratulationRequest),
    TaskKey.MASS_MESSAGING: (MessageService, "send_mass_message", ActionSchemas.MassMessagingRequest),
    TaskKey.ETERNAL_ONLINE: (AutomationService, "set_online_status", ActionSchemas.EmptyRequest),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "leave_groups_by_criteria", ActionSchemas.LeaveGroupsRequest),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "join_groups_by_criteria", ActionSchemas.JoinGroupsRequest),
}

# --- backend/app\tasks\__init__.py ---




# --- backend/app\arq_config.py ---

# backend/app/arq_config.py
from arq.connections import RedisSettings
from app.core.config import settings 
# Единый источник настроек Redis для ARQ.
# Используем базу данных Redis №4, чтобы не пересекаться с кэшем или limiter'ом.
redis_settings = RedisSettings(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    database=4
)

# --- backend/app\main.py ---

# backend/app/main.py

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis as AsyncRedis
# --- ИЗМЕНЕНИЕ: Импортируем необходимое для ARQ ---
from arq.connections import create_pool, ArqRedis
from app.arq_config import redis_settings
# --------------------------------------------------

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.admin import init_admin
from app.services.websocket_manager import redis_listener
from app.api.endpoints import (
    auth_router, users_router, proxies_router, tasks_router,
    stats_router, automations_router, billing_router, analytics_router,
    scenarios_router, notifications_router, posts_router, teams_router,
    websockets_router, support_router, task_history_router
)
from fastapi_limiter import FastAPILimiter
# Вызываем настройку логирования в самом начале
configure_logging()

# Создаем фоновую задачу для прослушивания Redis Pub/Sub для WebSockets
async def run_redis_listener(redis_client):
    await redis_listener(redis_client)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код, который выполнится при старте приложения
    
    # Пул для постановки задач в очередь ARQ из API
    arq_pool = await create_pool(redis_settings)
    app.state.arq_pool = arq_pool
    
    # --- ДОБАВЛЕНО: Инициализация Rate Limiter ---
    # Используем базу Redis №0 для limiter'а
    limiter_redis = AsyncRedis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        decode_responses=True
    )
    await FastAPILimiter.init(limiter_redis)
    # ---------------------------------------------
    
    # Клиент для WebSocket (использует базу 1)
    redis_client = AsyncRedis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1", 
        decode_responses=True
    )
    app.state.redis_client = redis_client
    
    # Запускаем listener в фоновом режиме
    listener_task = asyncio.create_task(run_redis_listener(redis_client))
    
    yield
    
    # Код, который выполнится при остановке приложения
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass # Ожидаемое исключение при отмене
        
    # ИСПРАВЛЕНИЕ ЗДЕСЬ
    await redis_client.aclose()
    await limiter_redis.aclose()
    await arq_pool.aclose()


# --- ВАЖНО: Вот тот самый объект 'app', который мы пытаемся импортировать ---
app = FastAPI(
    title="VK SMM Combine API",
    description="API для сервиса автоматизации SMM-задач ВКонтакте.",
    version="1.0.0",
    lifespan=lifespan
)

# --- Настройка CORS ---
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(',')]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Инициализация админ-панели SQLAdmin ---
init_admin(app, engine)

# --- Подключение всех роутеров API ---
api_prefix = "/api/v1"
app.include_router(auth_router, prefix=f"{api_prefix}/auth", tags=["Authentication"])
app.include_router(users_router, prefix=f"{api_prefix}/users", tags=["Users"])
app.include_router(proxies_router, prefix=f"{api_prefix}/proxies", tags=["Proxies"])
app.include_router(stats_router, prefix=f"{api_prefix}/stats", tags=["Statistics"])
app.include_router(automations_router, prefix=f"{api_prefix}/automations", tags=["Automations"])
app.include_router(billing_router, prefix=f"{api_prefix}/billing", tags=["Billing"])
app.include_router(analytics_router, prefix=f"{api_prefix}/analytics", tags=["Analytics"])
app.include_router(support_router, prefix=f"{api_prefix}/support", tags=["Support"])
app.include_router(scenarios_router, prefix=f"{api_prefix}/scenarios", tags=["Scenarios"])
app.include_router(notifications_router, prefix=f"{api_prefix}/notifications", tags=["Notifications"])
app.include_router(posts_router, prefix=f"{api_prefix}/posts", tags=["Posts"])
app.include_router(teams_router, prefix=f"{api_prefix}/teams", tags=["Teams"])
app.include_router(websockets_router, prefix=api_prefix, tags=["WebSockets"])
app.include_router(tasks_router, prefix=f"{api_prefix}/tasks", tags=["Tasks"])
app.include_router(task_history_router, prefix=f"{api_prefix}/tasks", tags=["Tasks"])

# --- backend/app\worker.py ---

# backend/app/worker.py
from arq import cron
from app.arq_config import redis_settings

# --- ИМПОРТЫ ИЗ НОВЫХ МОДУЛЕЙ ---
from app.tasks.cron_jobs import *
from app.tasks.maintenance_jobs import *
from app.tasks.profile_parser_jobs import *
from app.tasks.standard_tasks import *
from app.tasks.system_tasks import *

functions = [
    # Задачи из standard_tasks.py
    like_feed_task, add_recommended_friends_task, accept_friend_requests_task,
    remove_friends_by_criteria_task, view_stories_task, birthday_congratulation_task,
    mass_messaging_task, eternal_online_task, leave_groups_by_criteria_task,
    join_groups_by_criteria_task,
    publish_scheduled_post_task, run_scenario_from_scheduler_task,
]

cron_jobs = [
    cron(aggregate_daily_stats_job, hour=2, minute=5),
    cron(snapshot_all_users_metrics_job, hour=3),
    cron(clear_old_task_history_job, hour=4),
    cron(update_friend_request_statuses_job, hour={0, 4, 8, 12, 16, 20}, minute=0),
    cron(generate_all_heatmaps_job, hour=5),
    cron(check_expired_plans_job, minute={0, 15, 30, 45}),
    cron(run_standard_automations_job, minute=set(range(0, 60, 5))),
    cron(run_online_automations_job, minute={0, 10, 20, 30, 40, 50}),
]

async def startup(ctx):
    from arq.connections import create_pool
    ctx['redis_pool'] = await create_pool(redis_settings)
    print("Воркер ARQ запущен и готов к работе.")

async def shutdown(ctx):
    if 'redis_pool' in ctx: await ctx['redis_pool'].close()
    print("Воркер ARQ остановлен.")

class WorkerSettings:
    functions = functions
    cron_jobs = cron_jobs
    redis_settings = redis_settings
    on_startup = startup
    on_shutdown = shutdown

# --- backend/app\__init__.py ---



# --- backend/app\admin\auth.py ---

import secrets
from datetime import timedelta
from jose import jwt, JWTError
from fastapi import Request
from sqladmin.authentication import AuthenticationBackend

from app.db.models import User
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

# --- backend/app\admin\__init__.py ---

from sqladmin import Admin
from .auth import authentication_backend

# Импортируем все наши представления из модулей
from .views.user import UserAdmin
from .views.support import SupportTicketAdmin
from .views.payment import PaymentAdmin
from .views.stats import AutomationAdmin, DailyStatsAdmin, ActionLogAdmin

def init_admin(app, engine):
    admin = Admin(app, engine, authentication_backend=authentication_backend, title="SMM Combine Admin")
    
    # Регистрируем импортированные представления
    admin.add_view(UserAdmin)
    admin.add_view(SupportTicketAdmin)
    admin.add_view(PaymentAdmin)
    admin.add_view(AutomationAdmin)
    admin.add_view(DailyStatsAdmin)
    admin.add_view(ActionLogAdmin)

# --- backend/app\admin\views\payment.py ---

from sqladmin import ModelView
from app.db.models import Payment

class PaymentAdmin(ModelView, model=Payment):
    name_plural = "Платежи"
    icon = "fa-solid fa-ruble-sign"
    can_create = False
    can_edit = False
    can_delete = True
    
    column_list = [Payment.id, Payment.user, Payment.plan_name, Payment.amount, Payment.status, Payment.created_at]
    column_searchable_list = [Payment.user_id, "user.vk_id"]
    column_filters = [Payment.status, Payment.plan_name]
    column_default_sort = ("created_at", True)

# --- backend/app\admin\views\stats.py ---

from sqladmin import ModelView
from app.db.models import Automation, DailyStats, ActionLog

class AutomationAdmin(ModelView, model=Automation):
    name_plural = "Автоматизации"
    icon = "fa-solid fa-robot"
    column_list = [Automation.user, Automation.automation_type, Automation.is_active, Automation.last_run_at]
    column_searchable_list = [Automation.user_id, "user.vk_id"]
    column_filters = [Automation.automation_type, Automation.is_active]

class DailyStatsAdmin(ModelView, model=DailyStats):
    name_plural = "Дневная статистика"
    icon = "fa-solid fa-chart-line"
    can_create = False
    can_edit = False
    column_list = [c.name for c in DailyStats.__table__.c]
    column_default_sort = ("date", True)
    column_searchable_list = [DailyStats.user_id]

class ActionLogAdmin(ModelView, model=ActionLog):
    name_plural = "Логи действий"
    icon = "fa-solid fa-clipboard-list"
    can_create = False
    can_edit = False
    column_list = [ActionLog.id, ActionLog.user, ActionLog.action_type, ActionLog.message, ActionLog.status, ActionLog.timestamp]
    column_searchable_list = [ActionLog.user_id, "user.vk_id"]
    column_filters = [ActionLog.action_type, ActionLog.status]
    column_default_sort = ("timestamp", True)

# --- backend/app\admin\views\support.py ---

import datetime
from fastapi import Request
from sqladmin import ModelView, action
from app.db.models import SupportTicket, TicketMessage, TicketStatus, User
from app.core.config import settings
from app.db.session import AsyncSessionFactory

class TicketMessageAdmin(ModelView, model=TicketMessage):
    """Inline-представление для сообщений внутри тикета."""
    can_create = True
    can_edit = False
    can_delete = False
    can_list = False
    column_list = [TicketMessage.author, TicketMessage.message, TicketMessage.created_at]
    
    async def on_model_change(self, data: dict, model: TicketMessage, is_created: bool, request: Request) -> None:
        if is_created:
            async with AsyncSessionFactory() as session:
                admin_user = await session.get(User, int(settings.ADMIN_VK_ID))
                if admin_user:
                    model.author_id = admin_user.id
                    
                    # Обновляем статус тикета и время
                    ticket = await session.get(SupportTicket, model.ticket_id)
                    if ticket:
                        ticket.status = TicketStatus.IN_PROGRESS
                        ticket.updated_at = datetime.datetime.utcnow()

class SupportTicketAdmin(ModelView, model=SupportTicket):
    name = "Тикет"
    name_plural = "Техподдержка"
    icon = "fa-solid fa-headset"
    
    column_list = [SupportTicket.id, SupportTicket.user, SupportTicket.subject, SupportTicket.status, SupportTicket.updated_at]
    column_details_list = [SupportTicket.id, SupportTicket.user, SupportTicket.subject, SupportTicket.status, SupportTicket.created_at, SupportTicket.updated_at, SupportTicket.messages]
    
    column_searchable_list = [SupportTicket.id, SupportTicket.subject, "user.vk_id"]
    column_filters = [SupportTicket.status]
    column_default_sort = ("updated_at", True)
    
    form_excluded_columns = [SupportTicket.created_at, SupportTicket.updated_at]
    form_include_related = {"messages": {"model": TicketMessageAdmin}}

    @action(
        name="close_tickets", label="Закрыть тикет(ы)",
        confirmation_message="Уверены, что хотите закрыть выбранные тикеты?",
        add_in_list=True, add_in_detail=True
    )
    async def close_tickets_action(self, request: Request, pks: list[int]):
        async with AsyncSessionFactory() as session:
            for pk in pks:
                ticket = await session.get(SupportTicket, pk)
                if ticket:
                    ticket.status = TicketStatus.CLOSED
            await session.commit()
        return {"message": f"Закрыто тикетов: {len(pks)}"}

# --- backend/app\admin\views\user.py ---

# Содержит UserAdmin
from sqladmin import ModelView, action
from app.db.models import User
from datetime import timedelta, datetime, timezone
from fastapi import Request
from sqladmin import ModelView, action
from app.db.models import User
from app.db.session import AsyncSessionFactory
from app.core.plans import get_limits_for_plan

class UserAdmin(ModelView, model=User):
    name_plural = "Пользователи"
    icon = "fa-solid fa-users"
    
    column_list = [
        User.id, User.vk_id, User.plan, User.plan_expires_at,
        User.is_admin, User.created_at
    ]
    column_formatters = {
        User.vk_id: lambda m, a: f'<a href="https://vk.com/id{m.vk_id}" target="_blank">{m.vk_id}</a>'
    }
    column_searchable_list = [User.vk_id, User.id]
    column_filters = [User.plan, User.is_admin]
    column_default_sort = ("created_at", True)
    
    form_columns = [
        User.plan, User.plan_expires_at, User.is_admin, User.daily_likes_limit,
        User.daily_add_friends_limit, User.daily_message_limit, User.daily_posts_limit,
    ]
    
    @action(
        name="extend_subscription", label="Продлить подписку (+30 дней)",
        confirmation_message="Уверены, что хотите продлить подписку на 30 дней?",
        add_in_detail=True, add_in_list=True,
    )
    async def extend_subscription_action(self, request: Request, pks: list[int]):
        async with AsyncSessionFactory() as session:
            for pk in pks:
                user = await session.get(User, pk)
                if not user: continue
                
                start_date = user.plan_expires_at if user.plan_expires_at and user.plan_expires_at > datetime.now(timezone.utc) else datetime.now(timezone.utc)
                user.plan_expires_at = start_date + timedelta(days=30)
                
                if user.plan == "Expired":
                    user.plan = "Plus"
                    new_limits = get_limits_for_plan("Plus")
                    for key, value in new_limits.items():
                        setattr(user, key, value)

            await session.commit()
        return {"message": f"Подписка продлена для {len(pks)} пользователей."}

# --- backend/app\admin\views\__init__.py ---



# --- backend/app\api\dependencies.py ---

# backend/app/api/dependencies.py
from typing import Annotated, Dict, Any
from arq import ArqRedis
from fastapi import Depends, HTTPException, Request, status, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy import select, and_ 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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

# --- ИСПРАВЛЕННАЯ ЛОГИКА ---
async def get_current_active_profile(
    payload: Dict[str, Any] = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Определяет активный профиль на основе JWT токена.
    Эта функция ДОВЕРЯЕТ содержимому токена, так как эндпоинт /switch-profile
    уже проверил права доступа перед его выдачей.
    """
    manager_id_str = payload.get("sub")
    active_profile_id_str = payload.get("profile_id")

    if not manager_id_str:
        raise credentials_exception

    # Если 'profile_id' в токене нет, значит, пользователь работает со своим профилем.
    target_user_id = int(active_profile_id_str or manager_id_str)

    # Просто загружаем нужный профиль из БД.
    # Повторная проверка связи ManagedProfile здесь не нужна.
    active_profile = await db.get(User, target_user_id)
    
    if not active_profile:
        raise HTTPException(status_code=404, detail="Активный профиль не найден.")
        
    return active_profile
# --- КОНЕЦ ИСПРАВЛЕНИЯ ---


async def get_current_user_from_ws(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db) 
) -> User:
    payload = await _get_payload_from_string(token)
    profile_id = int(payload.get("profile_id") or payload.get("sub"))
    user = await db.get(User, profile_id)  
    if not user:
        raise credentials_exception
    return user

# --- backend/app\api\__init__.py ---



# --- backend/app\api\endpoints\analytics.py ---

# --- START OF FILE backend/app/api/endpoints/analytics.py ---

import datetime
from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, ProfileMetric, FriendRequestLog, PostActivityHeatmap
from app.api.dependencies import get_current_active_profile
from app.db.session import get_db
from app.api.schemas.analytics import (
    AudienceAnalyticsResponse, ProfileGrowthResponse, ProfileGrowthItem,
    ProfileSummaryResponse, FriendRequestConversionResponse, PostActivityHeatmapResponse,
    ProfileSummaryData
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.services.analytics_service import AnalyticsService
from app.services.event_emitter import SystemLogEmitter 

router = APIRouter()


@router.get("/audience", response_model=AudienceAnalyticsResponse)
@cache(expire=21600)
async def get_audience_analytics(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    emitter = SystemLogEmitter(task_name="analytics_endpoint") 
    service = AnalyticsService(db=db, user=current_user, emitter=emitter)
    try:
        return await service.get_audience_distribution()
    finally:
        if service.vk_api:
            await service.vk_api.close()

@router.get("/profile-summary", response_model=ProfileSummaryResponse)
@cache(expire=3600)
async def get_profile_summary(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """
    Возвращает текущие метрики профиля и динамику их изменения
    за последний день и неделю.
    """
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    week_ago = today - datetime.timedelta(days=7)

    stmt = select(ProfileMetric).where(
        ProfileMetric.user_id == current_user.id,
        ProfileMetric.date.in_([today, yesterday, week_ago])
    )
    result = await db.execute(stmt)
    metrics = {metric.date: metric for metric in result.scalars().all()}

    today_metrics = metrics.get(today)
    yesterday_metrics = metrics.get(yesterday)
    week_ago_metrics = metrics.get(week_ago)

    # ИСПРАВЛЕНИЕ: Безопасное создание DTO с явным маппингом полей
    if today_metrics:
        current_stats = ProfileSummaryData(
            friends=today_metrics.friends_count,
            followers=today_metrics.followers_count,
            photos=today_metrics.photos_count,
            wall_posts=today_metrics.wall_posts_count,
            recent_post_likes=today_metrics.recent_post_likes,
            recent_photo_likes=today_metrics.recent_photo_likes,
            total_post_likes=today_metrics.total_post_likes,
            total_photo_likes=today_metrics.total_photo_likes
        )
    else:
        current_stats = ProfileSummaryData()

    growth_daily = {}
    growth_weekly = {}
    
    # Используем поля схемы для итерации, чтобы ничего не пропустить
    fields_to_compare = ProfileSummaryData.model_fields.keys()
    model_field_map = {
        "friends": "friends_count", "followers": "followers_count", "photos": "photos_count",
        "wall_posts": "wall_posts_count",
        "recent_post_likes": "recent_post_likes",
        "recent_photo_likes": "recent_photo_likes",
        "total_post_likes": "total_post_likes",
        "total_photo_likes": "total_photo_likes",
    }

    for schema_field in fields_to_compare:
        model_field = model_field_map[schema_field]
        today_val = getattr(today_metrics, model_field, 0) if today_metrics else 0
        
        yesterday_val = getattr(yesterday_metrics, model_field, 0) if yesterday_metrics else 0
        growth_daily[schema_field] = today_val - yesterday_val
            
        week_ago_val = getattr(week_ago_metrics, model_field, 0) if week_ago_metrics else 0
        growth_weekly[schema_field] = today_val - week_ago_val

    return ProfileSummaryResponse(
        current_stats=current_stats,
        growth_daily=growth_daily,
        growth_weekly=growth_weekly
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
    
    # Используем ProfileGrowthItem для валидации и формирования ответа
    response_data = [ProfileGrowthItem(**row.__dict__) for row in data]

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
    
    conversion_rate = (accepted_total / sent_total * 100) if sent_total > 0 else 0.0

    return FriendRequestConversionResponse(
        sent_total=sent_total,
        accepted_total=accepted_total,
        conversion_rate=round(conversion_rate, 2)
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
        # Возвращаем пустую сетку, если данных еще нет
        return PostActivityHeatmapResponse(data=[[0]*24]*7)
        
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
from app.api.dependencies import get_current_manager_user, limiter

router = APIRouter()

class TokenRequest(BaseModel):
    vk_token: str


@router.post(
    "/vk",
    response_model=EnrichedTokenResponse,
    summary="Аутентификация или регистрация по токену VK",
    dependencies=[Depends(limiter)]
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
        user_data = {
            "vk_id": vk_id,
            "encrypted_vk_token": encrypted_token,
            "plan": PlanName.BASE.name,
            "plan_expires_at": datetime.now(UTC) + timedelta(days=14),
        }
        
        base_plan_limits = get_limits_for_plan(PlanName.BASE)
        
        user_model_columns = {c.name for c in User.__table__.columns}
        valid_limits_for_db = {
            key: value
            for key, value in base_plan_limits.items()
            if key in user_model_columns
        }
        user_data.update(valid_limits_for_db)
        
        user = User(**user_data)
        db.add(user)

    if str(vk_id) == settings.ADMIN_VK_ID:
        admin_limits = get_limits_for_plan(PlanName.PRO)
        user.is_admin = True
        # ИЗМЕНЕНО: Используем .name, чтобы в БД записалась строка "PRO"
        user.plan = PlanName.PRO.name
        user.plan_expires_at = None
        
        user_model_columns = {c.name for c in User.__table__.columns}
        for key, value in admin_limits.items():
            if key in user_model_columns:
                setattr(user, key, value)

    await db.flush()
    await db.refresh(user)

    user_id = user.id

    login_entry = LoginHistory(
        user_id=user_id,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown")
    )
    db.add(login_entry)
    
    await db.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
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
    
    # --- НАЧАЛО ИСПРАВЛЕННОЙ ЛОГИКИ ---
    # Загружаем все необходимые связи для проверки прав
    await db.refresh(manager, attribute_names=["managed_profiles", "team_membership"])
    if manager.team_membership:
        await db.refresh(manager.team_membership, attribute_names=["profile_accesses"])

    # 1. Начинаем собирать все ID профилей, к которым у пользователя есть доступ
    allowed_profile_ids = {manager.id} # Пользователь всегда может "переключиться" на себя

    # 2. Добавляем профили, которыми он управляет напрямую
    if manager.managed_profiles:
        allowed_profile_ids.update({p.profile_user_id for p in manager.managed_profiles})

    # 3. Добавляем профили, к которым ему дали доступ как члену команды
    if manager.team_membership and manager.team_membership.profile_accesses:
        allowed_profile_ids.update({p.profile_user_id for p in manager.team_membership.profile_accesses})

    # 4. Проверяем, есть ли желаемый ID в собранном списке
    if request_data.profile_id not in allowed_profile_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ к этому профилю запрещен.")
    # --- КОНЕЦ ИСПРАВЛЕННОЙ ЛОГИКИ ---

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
        # --- ИЗМЕНЕНИЕ ---
        auto_type = config_item.id
        # -----------------
        db_item = user_automations_db.get(auto_type)
        
        is_available = is_feature_available_for_plan(current_user.plan, auto_type)
        
        response_list.append(AutomationStatus(
            automation_type=auto_type,
            is_active=db_item.is_active if db_item else False,
            # --- ИЗМЕНЕНИЕ ---
            settings=db_item.settings if db_item else config_item.default_settings or {},
            name=config_item.name,
            description=config_item.description,
            # -----------------
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

    # --- ИЗМЕНЕНИЕ ---
    config_item = next((item for item in AUTOMATIONS_CONFIG if item.id == automation_type), None)
    # -----------------
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
            # --- ИЗМЕНЕНИЕ ---
            settings=request_data.settings or config_item.default_settings or {}
            # -----------------
        )
        db.add(automation)
    else:
        automation.is_active = request_data.is_active
        if request_data.settings is not None:
            automation.settings = request_data.settings
    
    await db.commit()
    await db.refresh(automation)
    
    return AutomationStatus(
        automation_type=automation.automation_type,
        is_active=automation.is_active,
        settings=automation.settings,
        # --- ИЗМЕНЕНИЕ ---
        name=config_item.name,
        description=config_item.description,
        # -----------------
        is_available=is_feature_available_for_plan(current_user.plan, automation_type)
    )

# --- backend/app\api\endpoints\billing.py ---

# --- START OF FILE backend/app/api/endpoints/billing.py ---

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
                "currency": "RUB",
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

    payment_response = {
        "id": f"test_payment_{uuid.uuid4()}",
        "status": "pending",
        "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=fake-order-id"}
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
        log.warn("webhook.invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    event_type = event.get("event")
    payment_data = event.get("object", {})
    payment_system_id = payment_data.get("id")
    
    log.info("webhook.received", event_type=event_type, payment_id=payment_system_id)
    
    if event_type == "payment.succeeded":
        if not payment_system_id:
            return {"status": "error", "message": "Payment ID missing."}

        query = select(Payment).where(Payment.payment_system_id == payment_system_id).with_for_update()
        payment = (await db.execute(query)).scalar_one_or_none()

        if not payment:
            log.warn("webhook.payment_not_found", payment_id=payment_system_id)
            return {"status": "ok"}

        if payment.status == "succeeded":
            log.info("webhook.already_processed", payment_id=payment.id)
            return {"status": "ok"}
        
        user = await db.get(User, payment.user_id, with_for_update=True)
        if not user:
            log.error("webhook.user_not_found", user_id=payment.user_id)
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
        for key, value in new_limits.items():
            if hasattr(user, key):
                setattr(user, key, value)

        payment.status = "succeeded"
        
        log.info("webhook.success", user_id=user.id, plan=user.plan, expires_at=user.plan_expires_at)
        
        # --- ИСПРАВЛЕНИЕ: Сохраняем все изменения в БД ---
        await db.commit()
        
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
import asyncio
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, AsyncGenerator
from arq.connections import ArqRedis

from app.db.session import get_db
from app.db.models import User, ScheduledPost
from app.api.dependencies import get_current_active_profile, get_arq_pool
# --- ИЗМЕНЕНИЕ: Добавляем новую схему ---
from app.api.schemas.posts import (
    PostCreate, PostRead, UploadedImagesResponse, PostBatchCreate, 
    UploadedImageResponse, UploadImageFromUrlRequest, UploadImagesFromUrlsRequest
)
from app.services.vk_api import VKAPI
from app.core.security import decrypt_data
from app.repositories.stats import StatsRepository
import structlog

log = structlog.get_logger(__name__)
router = APIRouter()

async def get_vk_api(current_user: User = Depends(get_current_active_profile)) -> AsyncGenerator[VKAPI, None]:
    vk_token = decrypt_data(current_user.encrypted_vk_token)
    if not vk_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен VK.")
    
    vk_api_client = VKAPI(access_token=vk_token)
    try:
        yield vk_api_client
    finally:
        await vk_api_client.close()

async def _download_image_from_url(url: str) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.pixiv.net/"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=20) as response:
                response.raise_for_status()
                return await response.read()
    except aiohttp.ClientError as e:
        log.error("image_download.failed", url=url, status_code=getattr(e, 'status', None), message=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Не удалось скачать изображение по URL: {e}")
    except Exception as e:
        log.error("image_download.unknown_error", url=url, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Внутренняя ошибка при скачивании изображения: {e}")

# --- НОВЫЙ ЭНДПОИНТ ДЛЯ ПАКЕТНОЙ ЗАГРУЗКИ ПО URL ---
@router.post("/upload-images-from-urls-batch", response_model=UploadedImagesResponse, summary="Загрузить несколько изображений по URL")
async def upload_images_from_urls_batch(
    request_data: UploadImagesFromUrlsRequest,
    vk_api: VKAPI = Depends(get_vk_api)
):
    """Принимает список URL, параллельно скачивает и загружает их в VK."""

    async def upload_one_url(url: str):
        try:
            image_bytes = await _download_image_from_url(url)
            return await vk_api.photos.upload_for_wall(image_bytes)
        except Exception as e:
            log.warn("batch_url_upload.single_url_error", url=url, error=str(e))
            return None

    tasks = [upload_one_url(str(url)) for url in request_data.image_urls]
    results = await asyncio.gather(*tasks)
    
    successful_attachments = [res for res in results if res is not None]
    
    if not successful_attachments:
        raise HTTPException(status_code=500, detail="Не удалось загрузить ни одно из изображений по указанным URL.")
        
    return UploadedImagesResponse(attachment_ids=successful_attachments)
# --- КОНЕЦ НОВОГО ЭНДПОИНТА ---

@router.post("/upload-image-from-url", response_model=UploadedImageResponse, summary="Загрузить изображение по URL")
async def upload_image_from_url(
    request_data: UploadImageFromUrlRequest,
    vk_api: VKAPI = Depends(get_vk_api)
):
    try:
        image_bytes = await _download_image_from_url(str(request_data.image_url))
        attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        log.error("post.upload_image_url.failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось обработать и загрузить изображение.")


@router.post("/upload-image-file", response_model=UploadedImageResponse, summary="Загрузить изображение с диска")
async def upload_image_file(
    vk_api: VKAPI = Depends(get_vk_api),
    image: UploadFile = File(...)
):
    try:
        image_bytes = await image.read()
        attachment_id = await vk_api.photos.upload_for_wall(image_bytes)
        return UploadedImageResponse(attachment_id=attachment_id)
    except Exception as e:
        log.error("post.upload_image_file.failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Не удалось загрузить изображение.")


@router.post("/upload-images-batch", response_model=UploadedImagesResponse, summary="Загрузить несколько изображений с диска")
async def upload_images_batch(
    vk_api: VKAPI = Depends(get_vk_api),
    images: List[UploadFile] = File(...)
):
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="Можно загрузить не более 10 изображений за раз.")

    async def upload_one(image: UploadFile):
        try:
            image_bytes = await image.read()
            return await vk_api.photos.upload_for_wall(image_bytes)
        except Exception as e:
            log.error("batch_upload.single_file_error", filename=image.filename, error=str(e))
            return None

    tasks = [upload_one(img) for img in images]
    results = await asyncio.gather(*tasks)
    
    successful_attachments = [res for res in results if res is not None]
    
    if not successful_attachments:
        raise HTTPException(status_code=500, detail="Не удалось загрузить ни одно из изображений.")
        
    return UploadedImagesResponse(attachment_ids=successful_attachments)

@router.post("/schedule-batch", response_model=List[PostRead], status_code=status.HTTP_201_CREATED, summary="Запланировать несколько постов")
async def schedule_batch_posts(
    batch_data: PostBatchCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    created_posts_db = []
    
    stats_repo = StatsRepository(db)
    today_stats = await stats_repo.get_or_create_today_stats(current_user.id)
    
    posts_to_create_count = len(batch_data.posts)
    if posts_to_create_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Список постов для планирования не может быть пустым.")

    if today_stats.posts_created_count + posts_to_create_count > current_user.daily_posts_limit:
        remaining = current_user.daily_posts_limit - today_stats.posts_created_count
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Достигнут дневной лимит на создание постов. Осталось: {remaining if remaining > 0 else 0}"
        )
    
    for post_data in batch_data.posts:
        new_post = ScheduledPost(
            user_id=current_user.id,
            vk_profile_id=current_user.vk_id,
            post_text=post_data.post_text,
            attachments=post_data.attachments or [],
            publish_at=post_data.publish_at
        )
        db.add(new_post)
        created_posts_db.append(new_post)

    if not created_posts_db:
        raise HTTPException(status_code=400, detail="Не удалось создать ни одного поста из пакета.")

    today_stats.posts_created_count += len(created_posts_db)
    
    await db.flush()

    for post in created_posts_db:
        job = await arq_pool.enqueue_job(
            'publish_scheduled_post_task',
            post_id=post.id,
            _defer_until=post.publish_at
        )
        post.arq_job_id = job.job_id

    await db.commit()
    
    for post in created_posts_db:
        await db.refresh(post)

    return created_posts_db

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
        friends_response = await vk_api.get_user_friends(user_id=current_user.vk_id, fields="sex")
    except VKAPIError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=f"Ошибка VK API: {e.message}")
    finally:
        # --- ИСПРАВЛЕНИЕ: Гарантированно закрываем сессию ---
        if vk_api:
            await vk_api.close()

    analytics = {"male_count": 0, "female_count": 0, "other_count": 0}
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Проверяем наличие ответа и ключа 'items'
    if friends_response and friends_response.get('items'):
        # Итерируемся по списку друзей, а не по всему словарю
        for friend in friends_response['items']:
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

# --- backend/app\api\endpoints\support.py ---

import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import List

from app.db.session import get_db
from app.db.models import User, SupportTicket, TicketMessage, TicketStatus
from app.api.dependencies import get_current_active_profile
from app.api.schemas.support import SupportTicketCreate, SupportTicketRead, TicketMessageCreate, SupportTicketList

router = APIRouter()

@router.get("", response_model=List[SupportTicketList])
async def get_my_tickets(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Получить список всех тикетов текущего пользователя."""
    stmt = select(SupportTicket).where(SupportTicket.user_id == current_user.id).order_by(SupportTicket.updated_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=SupportTicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    ticket_data: SupportTicketCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Создать новый тикет в техподдержку."""
    new_ticket = SupportTicket(
        user_id=current_user.id,
        subject=ticket_data.subject,
        status=TicketStatus.OPEN
    )
    
    first_message = TicketMessage(
        ticket=new_ticket,
        author_id=current_user.id,
        message=ticket_data.message
    )
    
    db.add(new_ticket)
    db.add(first_message)
    await db.commit()
    await db.refresh(new_ticket, attribute_names=['messages'])
    return new_ticket

@router.get("/{ticket_id}", response_model=SupportTicketRead)
async def get_ticket_details(
    ticket_id: int,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Получить детали тикета и всю переписку по нему."""
    stmt = select(SupportTicket).where(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).options(selectinload(SupportTicket.messages))
    
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден.")
    
    return ticket

@router.post("/{ticket_id}/messages", response_model=SupportTicketRead)
async def reply_to_ticket(
    ticket_id: int,
    message_data: TicketMessageCreate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Ответить на тикет."""
    # Получаем тикет и блокируем его для обновления
    stmt = select(SupportTicket).where(
        SupportTicket.id == ticket_id,
        SupportTicket.user_id == current_user.id
    ).with_for_update()
    
    ticket = (await db.execute(stmt)).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден.")
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Этот тикет закрыт.")

    new_message = TicketMessage(
        ticket_id=ticket.id,
        author_id=current_user.id,
        message=message_data.message
    )
    db.add(new_message)
    
    # Меняем статус на OPEN, если на него ответил пользователь (вдруг админ поставил IN_PROGRESS)
    ticket.status = TicketStatus.OPEN
    ticket.updated_at = datetime.datetime.utcnow()
    
    await db.commit()
    await db.refresh(ticket, attribute_names=['messages'])
    return ticket

# --- backend/app\api\endpoints\tasks.py ---

# backend/app/api/endpoints/tasks.py

# ОТВЕТСТВЕННОСТЬ: Запуск, предпросмотр и конфигурация новых задач.
from fastapi import APIRouter, Depends, Body, HTTPException, status, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel, ValidationError
from arq.connections import ArqRedis
import datetime

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile, get_arq_pool
from app.db.session import get_db
from app.repositories.stats import StatsRepository
from app.api.schemas.tasks import ActionResponse, PreviewResponse, TaskConfigResponse, TaskField
from app.core.plans import get_plan_config, is_feature_available_for_plan
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import TaskKey
from app.services.vk_api import VKAPIError
from app.tasks.service_maps import TASK_CONFIG_MAP
from app.tasks.task_maps import AnyTaskRequest, TASK_FUNC_MAP, PREVIEW_SERVICE_MAP

router = APIRouter()

# --- Вспомогательная функция (ИСПРАВЛЕНО) ---
async def _enqueue_task(
    user: User, db: AsyncSession, arq_pool: ArqRedis, task_key: str, request_data: BaseModel,
    original_task_name: Optional[str] = None,
    defer_until: Optional[datetime.datetime] = None
) -> TaskHistory:
    """
    Проверяет лимиты и ГОТОВИТ задачу к постановке в очередь.
    НЕ ДЕЛАЕТ COMMIT. Возвращает объект TaskHistory для дальнейшей обработки.
    """
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

    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key), None)
    task_display_name = original_task_name or (task_config.name if task_config else "Неизвестная задача")

    task_history = TaskHistory(
        user_id=user.id,
        task_name=task_display_name,
        status="PENDING",
        parameters=request_data.model_dump(exclude_unset=True)
    )
    db.add(task_history)
    await db.flush() # Используем flush, чтобы получить ID, но не коммитим
    await db.refresh(task_history)
    
    return task_history

# --- Эндпоинты ---
@router.get("/{task_key}/config", response_model=TaskConfigResponse, summary="Получить конфигурацию UI для задачи")
async def get_task_config(
    task_key: TaskKey,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_key.value), None)
    if not task_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Конфигурация для задачи не найдена.")

    stats_repo = StatsRepository(db)
    today_stats = await stats_repo.get_or_create_today_stats(current_user.id)
    
    fields = []

    if task_config.has_count_slider:
        limit_map = {
            TaskKey.ADD_RECOMMENDED: ("daily_add_friends_limit", "friends_added_count"),
            TaskKey.LIKE_FEED: ("daily_likes_limit", "likes_count"),
            TaskKey.REMOVE_FRIENDS: ("daily_leave_groups_limit", "friends_removed_count"),
            TaskKey.MASS_MESSAGING: ("daily_message_limit", "messages_sent_count"),
            TaskKey.JOIN_GROUPS: ("daily_join_groups_limit", "groups_joined_count"),
            TaskKey.LEAVE_GROUPS: ("daily_leave_groups_limit", "groups_left_count"),
        }
        
        limit_key, stat_key = limit_map.get(task_key, (None, None))
        
        if limit_key and stat_key:
            total_limit = getattr(current_user, limit_key, 100)
            used_today = getattr(today_stats, stat_key, 0)
            remaining_limit = total_limit - used_today
            max_val = max(0, remaining_limit)
        else:
            max_val = 1000

        fields.append(TaskField(
            name="count",
            type="slider",
            label=task_config.modal_count_label or "Количество",
            default_value=min(task_config.default_count or 20, max_val),
            max_value=max_val
        ))
    return TaskConfigResponse(display_name=task_config.name, has_filters=task_config.has_filters, fields=fields)


@router.post("/run/{task_key}", response_model=ActionResponse, summary="Запустить любую задачу по ее ключу")
async def run_any_task(
    task_key: TaskKey,
    request: Request,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool)
):
    try:
        raw_body = await request.json()
        
        task_config_tuple = TASK_CONFIG_MAP.get(task_key)
        if not task_config_tuple:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Конфигурация для задачи '{task_key.value}' не найдена.")
        
        RequestModel = task_config_tuple[2]
        request_data = RequestModel(**raw_body)
        
        publish_at_str = raw_body.get("publish_at")
        defer_until = datetime.datetime.fromisoformat(publish_at_str) if publish_at_str else None

    except (ValidationError, TypeError, ValueError) as e:
         raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    # --- НАЧАЛО ИСПРАВЛЕНИЯ: Единый процесс для всех задач ---
    # 1. Вызываем вспомогательную функцию, которая делает все проверки и готовит объект TaskHistory
    task_history = await _enqueue_task(
        user=current_user,
        db=db,
        arq_pool=arq_pool,
        task_key=task_key.value,
        request_data=request_data,
        defer_until=defer_until
    )
    
    # 2. Готовим параметры для ARQ
    task_func_name = TASK_FUNC_MAP[task_key]
    job_kwargs = {
        'task_history_id': task_history.id,
        **request_data.model_dump()
    }
    if defer_until:
        job_kwargs['_defer_until'] = defer_until
        
    # 3. Ставим задачу в очередь
    job = await arq_pool.enqueue_job(task_func_name, **job_kwargs)
    
    # 4. Обновляем ID задачи и коммитим ВСЕ изменения в одной транзакции
    task_history.arq_job_id = job.job_id
    await db.commit()
    
    # 5. Формируем ответ
    message = f"Задача '{task_history.task_name}' успешно добавлена в очередь."
    if defer_until:
        message = f"Задача '{task_history.task_name}' запланирована на {defer_until.strftime('%Y-%m-%d %H:%M:%S')}."
        
    return ActionResponse(message=message, task_id=job.job_id)
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---


@router.post("/preview/{task_key}", response_model=PreviewResponse, summary="Предварительный подсчет аудитории для задачи")
async def preview_task_audience(
    task_key: TaskKey,
    request_data: AnyTaskRequest = Body(...),
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    if task_key not in PREVIEW_SERVICE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Предпросмотр для задачи '{task_key.value}' не поддерживается."
        )

    class DummyEmitter:
        def __init__(self): self.user_id = current_user.id
        async def send_log(*args, **kwargs): pass
        async def send_stats_update(*args, **kwargs): pass

    service_instance = None
    try:
        ServiceClass, method_name, RequestModel = PREVIEW_SERVICE_MAP[task_key]
        validated_params = RequestModel(**request_data.model_dump())
        service_instance = ServiceClass(db=db, user=current_user, emitter=DummyEmitter())
        targets = await getattr(service_instance, method_name)(validated_params)
        return PreviewResponse(found_count=len(targets))
    except VKAPIError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=f"Ошибка VK API: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        if service_instance and hasattr(service_instance, 'vk_api') and service_instance.vk_api:
            await service_instance.vk_api.close()

# --- backend/app\api\endpoints\task_history.py ---

# backend/app/api/endpoints/task_history.py

# ОТВЕТСТВЕННОСТЬ: Просмотр истории задач и управление ими (отмена, повтор).
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel
from arq.connections import ArqRedis

from app.db.models import User, TaskHistory
from app.api.dependencies import get_current_active_profile, get_arq_pool
from app.db.session import get_db
from app.api.schemas.tasks import ActionResponse, PaginatedTasksResponse
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import TaskKey

from .tasks import _enqueue_task
from app.tasks.task_maps import AnyTaskRequest, PREVIEW_SERVICE_MAP

router = APIRouter()

@router.get("/history", response_model=PaginatedTasksResponse, summary="Получить историю выполненных задач")
async def get_user_task_history(
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None, description="Фильтр по статусу (PENDING, STARTED, SUCCESS, FAILURE, CANCELLED)")
):
    offset = (page - 1) * size
    base_query = select(TaskHistory).where(TaskHistory.user_id == current_user.id)
    if status and status.strip():
        base_query = base_query.where(TaskHistory.status == status.upper())

    tasks_query = base_query.order_by(TaskHistory.created_at.desc()).offset(offset).limit(size)
    count_query = select(func.count()).select_from(base_query.subquery())

    tasks = (await db.execute(tasks_query)).scalars().all()
    total = (await db.execute(count_query)).scalar_one()

    return PaginatedTasksResponse(items=tasks, total=total, page=page, size=size, has_more=(offset + len(tasks)) < total)


@router.post("/{task_history_id}/cancel", status_code=status.HTTP_202_ACCEPTED, summary="Отменить задачу")
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

    if task.arq_job_id:
        try:
            await arq_pool.abort_job(task.arq_job_id)
        except Exception:
            pass
    task.status = "CANCELLED"
    task.result = "Задача отменена пользователем."
    await db.commit()
    return {"message": "Запрос на отмену задачи отправлен."}


@router.post("/{task_history_id}/retry", response_model=ActionResponse, summary="Повторить неудавшуюся задачу")
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

    _, _, RequestModel = PREVIEW_SERVICE_MAP.get(TaskKey(task_key_str), (None, None, BaseModel))
    
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
    
    # --- ШАГ 1: Загружаем все необходимые данные из НАШЕЙ БД одним запросом ---
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
    
    # --- ШАГ 2: Собираем ВСЕ уникальные VK ID, которые нужно обогатить данными из VK ---
    all_vk_ids_to_fetch = set()
    # Добавляем VK ID всех участников команды
    for member in team_details.members:
        all_vk_ids_to_fetch.add(member.user.vk_id)
    # Добавляем VK ID всех управляемых профилей
    for mp in managed_profiles_db:
        all_vk_ids_to_fetch.add(mp.profile.vk_id)
    # Добавляем VK ID самого менеджера
    all_vk_ids_to_fetch.add(manager.vk_id)

    # --- ШАГ 3: Делаем ОДИН пакетный запрос к VK API ---
    vk_info_map = {}
    if all_vk_ids_to_fetch:
        vk_api = VKAPI(decrypt_data(manager.encrypted_vk_token))
        try:
            vk_ids_str = ",".join(map(str, all_vk_ids_to_fetch))
            # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
            user_infos = await vk_api.users.get(user_ids=vk_ids_str, fields="photo_50")
            if user_infos:
                vk_info_map = {info['id']: info for info in user_infos}
        finally:
            await vk_api.close()

    # --- ШАГ 4: Собираем ответ, используя предзагруженные данные ---
    members_response = []
    for member in team_details.members:
        member_vk_info = vk_info_map.get(member.user.vk_id, {})
        
        accesses = []
        member_access_map = {pa.profile_user_id for pa in member.profile_accesses}
        
        # Собираем все профили, к которым может быть доступ
        all_available_profiles = [mp.profile for mp in managed_profiles_db]
        
        for profile in all_available_profiles:
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
from app.api.schemas.users import TaskInfoResponse, FilterPresetCreate, FilterPresetRead, ManagedProfileRead, AnalyticsSettingsRead, AnalyticsSettingsUpdate
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
        user_info_vk_list = await vk_api.users.get(fields="photo_200,status,counters")
    except VKAPIError as e:
         raise HTTPException(
             status_code=status.HTTP_424_FAILED_DEPENDENCY, 
             detail=f"Ошибка VK API: {e.message}"
        )
    finally:
        await vk_api.close()

    if not user_info_vk_list or not isinstance(user_info_vk_list, list):
        raise HTTPException(status_code=404, detail="Не удалось получить информацию из VK.")
    
    user_info_vk = user_info_vk_list[0]


    is_plan_active = True
    plan_name = current_user.plan
    if current_user.plan_expires_at and current_user.plan_expires_at < datetime.utcnow():
        is_plan_active = False
        plan_name = PlanName.EXPIRED

    features = get_features_for_plan(plan_name)
    
    # Теперь user_info_vk - это словарь, и распаковка пройдет успешно
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
    # Переиспользуем эндпоинт, чтобы не дублировать логику
    return await read_users_me(current_user)

@router.put("/me/analytics-settings", response_model=AnalyticsSettingsRead)
async def update_analytics_settings(
    settings_data: AnalyticsSettingsUpdate,
    current_user: User = Depends(get_current_active_profile),
    db: AsyncSession = Depends(get_db)
):
    """Обновляет персональные настройки пользователя для сбора аналитики."""
    current_user.analytics_settings_posts_count = settings_data.posts_count
    current_user.analytics_settings_photos_count = settings_data.photos_count
    await db.commit()
    await db.refresh(current_user)
    return AnalyticsSettingsRead(
        posts_count=current_user.analytics_settings_posts_count,
        photos_count=current_user.analytics_settings_photos_count
    )

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
            response = await vk_api.friends.getRequests() # Метод VK API для заявок
            count = response.get("count", 0) if response else 0
        
        elif task_key == "remove_friends":
            # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
            user_info_list = await vk_api.users.get(user_ids=str(current_user.vk_id), fields="counters")
            if user_info_list:
                user_info = user_info_list[0]
                count = user_info.get("counters", {}).get("friends", 0)
    except VKAPIError as e:
        print(f"Could not fetch task info for {task_key} due to VK API error: {e}")
        count = 0
    finally:
        await vk_api.close()

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
        try:
            # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
            user_infos = await vk_api.users.get(user_ids=",".join(map(str, all_vk_ids)), fields="photo_50")
            if user_infos:
                vk_info_map = {info['id']: info for info in user_infos}
        finally:
            await vk_api.close()

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

# --- backend/app/api/endpoints/__init__.py ---

# Этот файл собирает все роутеры из других файлов в этой директории,
# чтобы их можно было удобно импортировать и зарегистрировать в main.py

from .auth import router as auth_router
from .users import router as users_router
from .proxies import router as proxies_router
from .stats import router as stats_router
from .automations import router as automations_router
from .billing import router as billing_router
from .analytics import router as analytics_router
from .scenarios import router as scenarios_router
from .notifications import router as notifications_router
from .posts import router as posts_router
from .teams import router as teams_router
from .websockets import router as websockets_router
from .support import router as support_router
from .tasks import router as tasks_router
from .task_history import router as task_history_router

# --- backend/app\api\schemas\actions.py ---

# --- backend/app/api/schemas/actions.py ---
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, List, Any, Dict
import re


class ActionFilters(BaseModel):
    sex: Optional[Literal[0, 1, 2]] = Field(0, description="0 - любой, 1 - жен, 2 - муж")
    is_online: Optional[bool] = False
    last_seen_hours: Optional[int] = Field(None, ge=1)
    allow_closed_profiles: bool = False
    status_keyword: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    only_with_photo: Optional[bool] = Field(False)
    remove_banned: Optional[bool] = True
    last_seen_days: Optional[int] = Field(None, ge=1)
    
class LikeAfterAddConfig(BaseModel):
    enabled: bool = False
    targets: List[Literal['avatar', 'wall']] = ['avatar']

# --- НОВАЯ СХЕМА ДЛЯ "УМНОЙ" ОТПРАВКИ ---
class HumanizedSendingConfig(BaseModel):
    enabled: bool = Field(False, description="Включить режим 'человечной' отправки (медленно, по одному)")
    speed: Literal["slow", "normal", "fast"] = Field("normal", description="Скорость набора и отправки")
    simulate_typing: bool = Field(True, description="Показывать статус 'набирает сообщение'")


# --- Обновленные модели для задач ---

class LikeFeedRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class AddFriendsRequest(BaseModel):
    count: int = Field(20, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    like_config: LikeAfterAddConfig = Field(default_factory=LikeAfterAddConfig)
    send_message_on_add: bool = False
    message_text: Optional[str] = Field(None, max_length=500)
    # ДОБАВЛЕНО: Настройки очеловечивания для приветственного сообщения
    humanized_sending: HumanizedSendingConfig = Field(default_factory=HumanizedSendingConfig)


class AcceptFriendsRequest(BaseModel):
    filters: ActionFilters = Field(default_factory=ActionFilters)

class RemoveFriendsRequest(BaseModel):
    count: int = Field(100, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)

class MassMessagingRequest(BaseModel):
    count: int = Field(50, ge=1)
    filters: ActionFilters = Field(default_factory=ActionFilters)
    message_text: str = Field(..., min_length=1, max_length=1000)
    attachments: Optional[List[str]] = Field(
        None,
        description="Список attachment ID (напр. 'photo123_456').",
        max_length=10
    )
    # ------------------
    only_new_dialogs: bool = Field(False)
    only_unread: bool = Field(False)
    humanized_sending: HumanizedSendingConfig = Field(default_factory=HumanizedSendingConfig)


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
    filters: ActionFilters = Field(default_factory=ActionFilters)
    only_new_dialogs: bool = Field(False)
    only_unread: bool = Field(False)
    humanized_sending: HumanizedSendingConfig = Field(default_factory=HumanizedSendingConfig)


class DaySchedule(BaseModel):
    """Схема для расписания на один день."""
    is_active: bool = True
    start_time: str = Field("09:00", description="Время начала в формате HH:MM")
    end_time: str = Field("23:00", description="Время окончания в формате HH:MM")

    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not re.match(r'^(?:[01]\d|2[0-3]):[0-5]\d$', v):
            raise ValueError('Неверный формат времени. Ожидается HH:MM')
        return v
    
    @model_validator(mode='after')
    def check_times_logic(self) -> 'DaySchedule':
        start = self.start_time
        end = self.end_time
        if start >= end:
            raise ValueError('Время начала должно быть раньше времени окончания')
        return self

class EternalOnlineRequest(BaseModel):
    """
    ФИНАЛЬНАЯ ВЕРСИЯ: Отдельная, полноценная модель для задачи "Статус 'Онлайн'".
    """
    mode: Literal["schedule", "always"] = "schedule"
    humanize: bool = True
    schedule_weekly: Dict[Literal["1", "2", "3", "4", "5", "6", "7"], DaySchedule] = Field(
        default_factory=dict
    )

# --- backend/app\api\schemas\analytics.py ---

# --- START OF FILE backend/app/api/schemas/analytics.py ---

from pydantic import BaseModel, Field
from typing import List, Dict, Any
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

class ProfileSummaryData(BaseModel):
    friends: int = 0
    followers: int = 0
    photos: int = 0
    wall_posts: int = 0
    recent_post_likes: int = 0
    recent_photo_likes: int = 0
    total_post_likes: int = 0
    total_photo_likes: int = 0

class ProfileSummaryResponse(BaseModel):
    current_stats: ProfileSummaryData
    growth_daily: Dict[str, int]
    growth_weekly: Dict[str, int]


class ProfileGrowthItem(BaseModel):
    date: date
    friends_count: int
    followers_count: int
    photos_count: int
    wall_posts_count: int
    recent_post_likes: int
    recent_photo_likes: int
    total_post_likes: int
    total_photo_likes: int


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

# backend/app/api/schemas/posts.py
from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from datetime import datetime
from typing import List, Optional

class PostBase(BaseModel):
    post_text: Optional[str] = Field(None, max_length=4000)
    publish_at: datetime

class PostCreate(PostBase):
    attachments: Optional[List[str]] = Field(
        default_factory=list, 
        description="Список готовых attachment ID (photo_id, etc.). Не более 10.",
        max_length=10 # <--- ИЗМЕНЕНИЕ: max_items -> max_length
    )

class PostRead(PostBase):
    id: int
    vk_profile_id: int
    attachments: Optional[List[str]] = None
    status: str
    vk_post_id: Optional[str] = None
    error_message: Optional[str] = None
    arq_job_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UploadedImageResponse(BaseModel): 
    attachment_id: str

class UploadImageFromUrlRequest(BaseModel):
    image_url: HttpUrl

class UploadedImagesResponse(BaseModel):
    attachment_ids: List[str]

class UploadImagesFromUrlsRequest(BaseModel):
    image_urls: List[HttpUrl] = Field(..., description="Список URL изображений для загрузки. Не более 10.", max_length=10) # <--- ИЗМЕНЕНИЕ: max_items -> max_length

class PostBatchCreate(BaseModel):
    posts: List[PostCreate]

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

# --- backend/app\api\schemas\support.py ---

from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import List

# --- Схемы для сообщений ---
class TicketMessageRead(BaseModel):
    id: int
    author_id: int
    message: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TicketMessageCreate(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)

# --- Схемы для тикетов ---
class SupportTicketRead(BaseModel):
    id: int
    user_id: int
    subject: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    messages: List[TicketMessageRead] = []
    model_config = ConfigDict(from_attributes=True)
    
class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=5, max_length=100)
    message: str = Field(..., min_length=10, max_length=5000)

class SupportTicketList(BaseModel):
    """Схема для отображения в списке, без сообщений."""
    id: int
    subject: str
    status: str
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

# --- backend/app\api\schemas\tasks.py ---

# backend/app/api/schemas/tasks.py
import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Literal, Optional, Dict, Any

# --- Схема для ответа после запуска любой задачи ---
class ActionResponse(BaseModel):
    status: str = "success"
    message: str
    task_id: str

class TaskHistoryRead(BaseModel):
    id: int
    arq_job_id: Optional[str] = None
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

class PreviewResponse(BaseModel):
    found_count: int

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

class AnalyticsSettingsUpdate(BaseModel):
    posts_count: int = Field(100, ge=10, le=500, description="Количество недавних постов для анализа лайков.")
    photos_count: int = Field(200, ge=10, le=1000, description="Количество недавних фото для анализа лайков.")

class AnalyticsSettingsRead(AnalyticsSettingsUpdate):
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
    BASE = "BASE"
    PLUS = "PLUS"
    PRO = "PRO"
    AGENCY = "AGENCY"
    EXPIRED = "EXPIRED"

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

class CronSettings:
    # Время в секундах, на которое блокируется запуск однотипных cron-задач,
    # чтобы избежать двойного выполнения при высокой нагрузке. 4 минуты.
    AUTOMATION_JOB_LOCK_EXPIRATION_SECONDS: int = 240

    # Шанс (от 0.0 до 1.0), с которым "Интеллектуальное присутствие"
    # пропустит 10-минутный цикл для имитации человеческого перерыва.
    HUMANIZE_ONLINE_SKIP_CHANCE: float = 0.15

    # Записи в истории задач старше этого количества дней будут удалены для PRO/Agency тарифов.
    TASK_HISTORY_RETENTION_DAYS_PRO: int = 90

    # Записи в истории задач старше этого количества дней будут удалены для бесплатных тарифов.
    TASK_HISTORY_RETENTION_DAYS_BASE: int = 30

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
    # Эта функция теперь будет корректно работать, т.к. user.plan
    # будет хранить системное имя ("BASE", "PRO" и т.д.)
    key = plan_name.name if isinstance(plan_name, PlanName) else plan_name
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG["EXPIRED"]) # Используем строковый ключ "EXPIRED"
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
    # ИЗМЕНЕНО: Ключевое исправление.
    # Мы используем .name для получения строкового ключа, чтобы избежать KeyError.
    key = plan_name if isinstance(plan_name, str) else plan_name.name
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG[PlanName.EXPIRED.name])
    
    available_features = plan_model.available_features
    
    if available_features == "*":
        return True
    
    return feature_id in available_features

def get_features_for_plan(plan_name: PlanName | str) -> list[str]:
    """
    Возвращает полный список доступных ключей фич для тарифного плана.
    Обрабатывает wildcard '*' для PRO тарифов.
    """
    # ИЗМЕНЕНО: Аналогичное исправление для консистентности.
    key = plan_name if isinstance(plan_name, str) else plan_name.name
    plan_model = PLAN_CONFIG.get(key, PLAN_CONFIG[PlanName.EXPIRED.name])
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
from typing import List, Literal, Optional, Dict, Any

class AutomationConfig(BaseModel):
    id: str
    name: str
    description: str
    has_filters: bool
    has_count_slider: bool
    modal_count_label: Optional[str] = None
    default_count: Optional[int] = None
    group: Optional[Literal["standard", "online", "content"]] = "standard"
    default_settings: Optional[Dict[str, Any]] = None

class PlanPeriod(BaseModel):
    months: int = Field(..., gt=0)
    discount_percent: float = Field(..., ge=0, le=100)

class PlanLimits(BaseModel):
    daily_likes_limit: int = Field(..., ge=0)
    daily_add_friends_limit: int = Field(..., ge=0)
    daily_message_limit: int = Field(..., ge=0) 
    daily_posts_limit: int = Field(..., ge=0)   
    daily_join_groups_limit: int = Field(..., ge=0)
    daily_leave_groups_limit: int = Field(..., ge=0)
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

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0}
)

AsyncSessionFactory = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

# --- backend/app\db\__init__.py ---



# --- backend/app\db\models\analytics.py ---

# --- START OF FILE backend/app/db/models/analytics.py ---

import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, BigInteger,
    UniqueConstraint, JSON, Index, Date, Enum, text
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
    posts_created_count = Column(Integer, nullable=False, server_default=text('0'))
    groups_joined_count = Column(Integer, nullable=False, server_default=text('0'))
    groups_left_count = Column(Integer, nullable=False, server_default=text('0'))
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
    
    friends_count = Column(Integer, nullable=False, default=0)
    followers_count = Column(Integer, nullable=False, default=0)
    photos_count = Column(Integer, nullable=False, default=0)
    wall_posts_count = Column(Integer, nullable=False, default=0)
    
    # <<< ИЗМЕНЕНО: Поля для лайков разделены >>>
    recent_post_likes = Column(Integer, nullable=False, default=0)
    recent_photo_likes = Column(Integer, nullable=False, default=0)
    total_post_likes = Column(Integer, nullable=False, default=0)
    total_photo_likes = Column(Integer, nullable=False, default=0)
    
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
    last_updated_at = Column(DateTime(timezone=True), default=datetime.datetime.now(datetime.UTC), onupdate=datetime.datetime.now(datetime.UTC))
    user = relationship("User", back_populates="heatmap")

class FriendRequestLog(Base):
    __tablename__ = "friend_request_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_vk_id = Column(BigInteger, nullable=False, index=True)
    status = Column(Enum(FriendRequestStatus), nullable=False, default=FriendRequestStatus.pending, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now(datetime.UTC), index=True)
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
    Column, Integer, String, DateTime, ForeignKey, Text,
    UniqueConstraint, Boolean, JSON, Enum
)
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

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

class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.datetime.utcnow)
    
    user = relationship("User")
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketMessage.created_at")

class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False) # ID автора (юзер или админ)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    
    ticket = relationship("SupportTicket", back_populates="messages")
    author = relationship("User")

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
    arq_job_id = Column(String, unique=True, nullable=True, index=True)
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
    arq_job_id = Column(String, nullable=True, unique=True)
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
from app.core.constants import PlanName

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    vk_id = Column(BigInteger, unique=True, index=True, nullable=False)
    encrypted_vk_token = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    plan = Column(String, nullable=False, server_default=PlanName.BASE.value)
    plan_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_admin = Column(Boolean, nullable=False, server_default='false')
    daily_likes_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_add_friends_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_message_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_posts_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_join_groups_limit = Column(Integer, nullable=False, server_default=text('0'))
    daily_leave_groups_limit = Column(Integer, nullable=False, server_default=text('0'))
    delay_profile = Column(Enum(DelayProfile), nullable=False, server_default=DelayProfile.normal.name)
    analytics_settings_posts_count = Column(Integer, nullable=False, server_default=text('100'))
    analytics_settings_photos_count = Column(Integer, nullable=False, server_default=text('200'))

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
from collections import Counter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import PostActivityHeatmap, User
from app.services.vk_api import VKAPIError
from app.api.schemas.analytics import AudienceAnalyticsResponse, AudienceStatItem, SexDistributionResponse
import structlog

log = structlog.get_logger(__name__)

# --- Вспомогательные функции, которые были в эндпоинте ---
def _calculate_age(bdate: str) -> int | None:
    try:
        parts = bdate.split('.')
        if len(parts) == 3:
            birth_date = datetime.datetime.strptime(bdate, "%d.%m.%Y")
            today = datetime.date.today()
            return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except (ValueError, TypeError):
        return None
    return None

def _get_age_group(age: int) -> str:
    if age < 18: return "< 18"
    if 18 <= age <= 24: return "18-24"
    if 25 <= age <= 34: return "25-34"
    if 35 <= age <= 44: return "35-44"
    if age >= 45: return "45+"
    return "Не указан"
# --- Конец вспомогательных функций ---


class AnalyticsService(BaseVKService):

    # --- НОВЫЙ МЕТОД, В КОТОРЫЙ ПЕРЕНЕСЕНА ВСЯ ЛОГИКА ---
    async def get_audience_distribution(self) -> AudienceAnalyticsResponse:
        """
        Получает друзей пользователя из VK и рассчитывает распределение
        по городам, возрасту и полу.
        """
        await self._initialize_vk_api()
        
        friends = await self.vk_api.get_user_friends(user_id=self.user.vk_id, fields="sex,bdate,city")
        if not friends:
            return AudienceAnalyticsResponse(city_distribution=[], age_distribution=[], sex_distribution=[])

        # Расчет по городам
        city_counter = Counter(
            friend['city']['title']
            for friend in friends
            if friend.get('city') and friend.get('city', {}).get('title') and not friend.get('deactivated')
        )
        top_cities = [
            AudienceStatItem(name=city, value=count)
            for city, count in city_counter.most_common(5)
        ]

        # Расчет по возрасту
        ages = [_calculate_age(friend['bdate']) for friend in friends if friend.get('bdate') and not friend.get('deactivated')]
        age_groups = [_get_age_group(age) for age in ages if age is not None]
        age_counter = Counter(age_groups)
        age_distribution = [
            AudienceStatItem(name=group, value=count)
            for group, count in sorted(age_counter.items())
        ]

        # Расчет по полу
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
    # --- КОНЕЦ НОВОГО МЕТОДА ---

    async def generate_post_activity_heatmap(self):
        await self._initialize_vk_api()
        
        try:
            friends = await self.vk_api.get_user_friends(self.user.vk_id, fields="last_seen")
        except VKAPIError as e:
            log.error("heatmap.vk_error", user_id=self.user.id, error=str(e))
            return
        
        if not friends:
            return

        heatmap = [[0 for _ in range(24)] for _ in range(7)]
        now = datetime.datetime.utcnow()
        two_weeks_ago = now - datetime.timedelta(weeks=2)

        for friend in friends:
            last_seen_data = friend.get("last_seen")
            if not last_seen_data or not (seen_timestamp := last_seen_data.get("time")):
                continue
            
            seen_time = datetime.datetime.fromtimestamp(seen_timestamp, tz=pytz.UTC)
            
            if seen_time > two_weeks_ago:
                heatmap[seen_time.weekday()][seen_time.hour] += 1
        
        max_activity = max(max(row) for row in heatmap)
        normalized_heatmap = heatmap
        if max_activity > 0:
            normalized_heatmap = [[int((count / max_activity) * 100) for count in row] for row in heatmap]
        
        stmt = insert(PostActivityHeatmap).values(
            user_id=self.user.id,
            heatmap_data={"data": normalized_heatmap},
        ).on_conflict_do_update(
            index_elements=['user_id'],
            set_={"heatmap_data": {"data": normalized_heatmap}, "last_updated_at": datetime.datetime.utcnow()}
        )
        await self.db.execute(stmt)
        await self.db.commit()
        log.info("heatmap.generated", user_id=self.user.id)

# --- backend/app\services\automation_service.py ---

# --- backend/app/services/automation_service.py ---
import datetime
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import SentCongratulation
from app.api.schemas.actions import BirthdayCongratulationRequest, EternalOnlineRequest
from app.services.vk_user_filter import apply_filters_to_profiles
from app.services.message_service import MessageService
from app.services.message_humanizer import MessageHumanizer
from typing import List, Dict, Any

class AutomationService(BaseVKService):
    """
    Сервис для выполнения автоматизаций, которые не вписываются
    в другие категории (например, поздравления, поддержание статуса).
    """

    async def get_birthday_congratulation_targets(self, params: BirthdayCongratulationRequest) -> List[Dict[str, Any]]:
        """
        Находит друзей-именинников и применяет к ним все фильтры.
        Используется для предпросмотра и для выполнения задачи.
        """
        await self._initialize_vk_api()
        friends_response = await self.vk_api.get_user_friends(self.user.vk_id, fields="bdate,sex,online,last_seen,is_closed,status,city")
        if not friends_response or not friends_response.get('items'):
            return []

        friends = friends_response.get('items', [])
        today = datetime.date.today()
        today_str = f"{today.day}.{today.month}"
        
        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
        # Итерируемся по списку друзей, а не по всему ответу API
        birthday_friends_raw = [f for f in friends if f.get("bdate") and f.get("bdate").startswith(today_str)]
        if not birthday_friends_raw:
            return []
            
        await self.emitter.send_log(f"Найдено именинников: {len(birthday_friends_raw)} чел. Применяем фильтры...", "info")
        
        birthday_friends_filtered = await apply_filters_to_profiles(birthday_friends_raw, params.filters)
        if not birthday_friends_filtered:
            return []
        
        if params.only_new_dialogs or params.only_unread:
            message_service = MessageService(self.db, self.user, self.emitter)
            # API уже инициализирован, можно использовать напрямую
            message_service.vk_api = self.vk_api
            final_targets = await message_service.filter_targets_by_conversation_status(
                birthday_friends_filtered, params.only_new_dialogs, params.only_unread
            )
        else:
            final_targets = birthday_friends_filtered

        return final_targets

    async def congratulate_friends_with_birthday(self, params: BirthdayCongratulationRequest):
        """
        Выполняет логику поздравления друзей с Днем Рождения.
        """
        return await self._execute_logic(self._congratulate_friends_logic, params)

    async def _congratulate_friends_logic(self, params: BirthdayCongratulationRequest):
        """
        Приватный метод с основной логикой поздравления.
        """
        await self.emitter.send_log("Запуск задачи: Поздравление друзей с Днем Рождения.", "info")
        stats = await self._get_today_stats()
        
        final_targets = await self.get_birthday_congratulation_targets(params)
        if not final_targets:
            await self.emitter.send_log("После всех фильтров не осталось именинников для поздравления.", "success")
            return
            
        await self.emitter.send_log(f"К поздравлению готово: {len(final_targets)} чел. Проверяем, кого уже поздравили...", "info")
        current_year = datetime.date.today().year
        stmt = select(SentCongratulation.friend_vk_id).where(
            and_(SentCongratulation.user_id == self.user.id, SentCongratulation.year == current_year)
        )
        already_congratulated_ids = {row[0] for row in (await self.db.execute(stmt)).all()}
        targets_to_process = [friend for friend in final_targets if friend['id'] not in already_congratulated_ids]

        if not targets_to_process:
            await self.emitter.send_log("Все найденные именинники на сегодня уже были поздравлены.", "success")
            return

        await self.emitter.send_log(f"Начинаем отправку поздравлений для {len(targets_to_process)} чел.", "info")
        processed_count = 0

        for friend in targets_to_process:
            # Проверяем лимит перед каждой отправкой
            if stats.messages_sent_count >= self.user.daily_message_limit:
                await self.emitter.send_log(f"Достигнут дневной лимит сообщений ({self.user.daily_message_limit}). Поздравления остановлены.", "warning")
                break

            friend_id = friend['id']
            sex = friend.get("sex")
            template = params.message_template_default
            if sex == 2 and params.message_template_male:
                template = params.message_template_male
            elif sex == 1 and params.message_template_female:
                template = params.message_template_female
            
            is_sent_successfully = False
            if params.humanized_sending.enabled:
                humanizer = MessageHumanizer(self.vk_api, self.emitter)
                sent_count = await humanizer.send_messages_sequentially(
                    targets=[friend], template=template,
                    speed=params.humanized_sending.speed,
                    simulate_typing=params.humanized_sending.simulate_typing
                )
                if sent_count > 0:
                    is_sent_successfully = True
            else:
                message = template.replace("{name}", friend.get("first_name", ""))
                url = f"https://vk.com/id{friend_id}"
                await self.humanizer.think(action_type='message')
                if await self.vk_api.send_message(friend_id, message):
                    await self.emitter.send_log(f"Успешно отправлено поздравление для {friend.get('first_name', '')}", "success", target_url=url)
                    is_sent_successfully = True

            # Если отправка удалась, обновляем статистику и логи
            if is_sent_successfully:
                processed_count += 1
                await self._increment_stat(stats, 'messages_sent_count')
                insert_stmt = insert(SentCongratulation).values(user_id=self.user.id, friend_vk_id=friend_id, year=current_year).on_conflict_do_nothing()
                await self.db.execute(insert_stmt)

        await self.emitter.send_log(f"Задача завершена. Отправлено поздравлений: {processed_count}.", "success")
        
    async def set_online_status(self, params: EternalOnlineRequest):
        """
        Устанавливает статус "онлайн" для пользователя.
        """
        return await self._execute_logic(self._set_online_status_logic)

    async def _set_online_status_logic(self):
        """
        Непосредственно вызывает метод VK API для установки статуса.
        """
        await self.emitter.send_log("Поддержание статуса 'онлайн'...", "debug")
        await self.vk_api.account.setOnline()

# --- backend/app\services\base.py ---

# --- backend/app/services/base.py ---

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
        """Инициализирует VKAPI клиент и Humanizer, если они еще не созданы."""
        if self.vk_api:
            return

        vk_token = decrypt_data(self.user.encrypted_vk_token)
        proxy_url = await self._get_working_proxy()
        
        self.vk_api = VKAPI(access_token=vk_token, proxy=proxy_url)
        self.humanizer = Humanizer(delay_profile=self.user.delay_profile, logger_func=self.emitter.send_log)

    async def _get_working_proxy(self) -> str | None:
        """Выбирает случайный рабочий прокси из списка пользователя."""
        # Предполагаем, что user.proxies всегда загружены благодаря selectinload в `arq_task_runner`
        working_proxies = [p for p in self.user.proxies if p.is_working]
        if not working_proxies:
            return None
        
        chosen_proxy = random.choice(working_proxies)
        return decrypt_data(chosen_proxy.encrypted_proxy_url)

    async def _get_today_stats(self) -> DailyStats:
        """Получает или создает запись о статистике за сегодня."""
        return await self.stats_repo.get_or_create_today_stats(self.user.id)

    async def _increment_stat(self, stats: DailyStats, field_name: str, value: int = 1):
        """Безопасно увеличивает значение в статистике и отправляет обновление в UI."""
        current_value = getattr(stats, field_name, 0)
        setattr(stats, field_name, current_value + value)
        # Отправляем в UI только новое значение для конкретного поля
        await self.emitter.send_stats_update({f"{field_name}_today": getattr(stats, field_name)})

    async def _execute_logic(self, logic_func, *args, **kwargs):
        """
        Универсальный метод-обертка для выполнения основной логики сервиса.
        Управляет инициализацией и закрытием соединений.
        ТРАНЗАКЦИЯМИ НЕ УПРАВЛЯЕТ.
        """
        await self._initialize_vk_api()
        try:
            # Просто выполняем логику. Коммит/откат будет в вызывающем коде (arq_task_runner).
            result = await logic_func(*args, **kwargs)
            return result
        except Exception:
            raise
        finally:
            if self.vk_api:
                await self.vk_api.close()

# --- backend/app\services\event_emitter.py ---

# --- backend/app/services/event_emitter.py ---

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
    """
    Отправляет события в Redis Pub/Sub для实时-обновлений в UI пользователя.
    """
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.user_id: int | None = None
        self.task_history_id: int | None = None

    def set_context(self, user_id: int, task_history_id: int | None = None):
        self.user_id = user_id
        self.task_history_id = task_history_id

    async def _publish(self, channel: str, message: Dict[str, Any]):
        if not self.user_id:
            # Вместо ValueError используем structlog для логирования, чтобы не прерывать выполнение
            structlog.get_logger(__name__).warn("event_emitter.user_id_not_set")
            return
        await self.redis.publish(channel, json.dumps(message))

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        payload = {
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
        if not self.user_id: return
        
        new_notification = Notification(user_id=self.user_id, message=message, level=level)
        db.add(new_notification)
        await db.flush()
        await db.refresh(new_notification)
        
        payload = { 
            "id": new_notification.id, "message": new_notification.message, "level": new_notification.level,
            "is_read": new_notification.is_read, "created_at": new_notification.created_at.isoformat() 
        }
        await self._publish(f"ws:user:{self.user_id}", {"type": "new_notification", "payload": payload})


# --- ИСПРАВЛЕНИЕ: Объединенный и улучшенный класс-заглушка ---
class SystemLogEmitter:
    """
    Эмиттер-заглушка для фоновых задач (cron) и сервисов, не требующих UI-отклика.
    Выводит логи в structlog и создает системные уведомления в БД, 
    полностью имитируя интерфейс RedisEventEmitter для совместимости.
    """
    def __init__(self, task_name: str):
        self.log = structlog.get_logger(task_name)
        self.user_id: int | None = None
        self.task_history_id: int | None = None # Для совместимости интерфейса

    def set_context(self, user_id: int, task_history_id: int | None = None):
        """Привязывает ID пользователя к логам для удобства фильтрации и отладки."""
        self.user_id = user_id
        self.task_history_id = task_history_id
        # bind добавляет user_id ко всем последующим логам от этого экземпляра
        self.log = self.log.bind(user_id=user_id)

    async def send_log(self, message: str, status: LogLevel, target_url: str | None = None):
        """Преобразует статусы в уровни логирования structlog."""
        # Находим нужный метод логгера (info, warning, error), по умолчанию info
        log_method = getattr(self.log, status, self.log.info)
        log_method(message, url=target_url, status_from_emitter=status)

    async def send_stats_update(self, stats_dict: Dict[str, Any]):
        """Обновления статистики для UI не нужны в фоновых задачах, просто игнорируем."""
        pass

    async def send_task_status_update(self, *args, **kwargs):
        """Обновления статуса задачи для UI не нужны, игнорируем."""
        pass

    async def send_system_notification(self, db: AsyncSession, message: str, level: LogLevel):
        """Системные уведомления от фоновых задач также создаем в БД."""
        if self.user_id:
             new_notification = Notification(user_id=self.user_id, message=message, level=level)
             db.add(new_notification)
             # Коммит будет выполнен в вызывающей функции (в сервисе или задаче)
             self.log.info("system_notification.created", message=message, level=level)

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

        await self.humanizer.read_and_scroll()
        response = await self.vk_api.newsfeed.get(count=params.count * 2, filters=newsfeed_filter)

        if not response or not response.get('items'):
            await self.emitter.send_log("Посты в ленте не найдены. Задача завершена.", "warning")
            return

        posts = [p for p in response.get('items', []) if p.get('type') in ['post', 'photo']]
        await self.emitter.send_log(f"Найдено постов в ленте: {len(posts)}. Применяем фильтры...", "info")
        
        author_ids = [abs(p['source_id']) for p in posts if p.get('source_id', 0) > 0]
        
        filtered_author_ids = set(author_ids)
        if author_ids:
            author_profiles = await self._get_user_profiles(list(set(author_ids)))
            filtered_authors = await apply_filters_to_profiles(author_profiles, params.filters)
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

            url_prefix = "wall" if item_type == "post" else "photo"
            url = f"https://vk.com/{url_prefix}{owner_id}_{item_id}"

            await self.humanizer.think(action_type='like')
            result = await self.vk_api.likes.add(item_type, owner_id, item_id)
            
            if result and 'likes' in result:
                processed_count += 1
                await self._increment_stat(stats, 'likes_count')
                await self.emitter.send_log(f"Поставлен лайк ({processed_count}/{params.count})", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось поставить лайк. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Поставлено лайков: {processed_count}.", "success")
        
    async def _get_user_profiles(self, user_ids: List[int]) -> List[Dict[str, Any]]:
        if not user_ids: return []
        
        all_profiles = []
        for i in range(0, len(user_ids), 1000):
            chunk = user_ids[i:i + 1000]
            ids_str = ",".join(map(str, chunk))
            profiles = await self.vk_api.users.get(user_ids=ids_str)
            if profiles:
                all_profiles.extend(profiles)
        return all_profiles

# --- backend/app\services\friend_management_service.py ---

# --- backend/app/services/friend_management_service.py ---
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import RemoveFriendsRequest

class FriendManagementService(BaseVKService):

    async def get_remove_friends_targets(self, params: RemoveFriendsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает список друзей и фильтрует их по заданным критериям
        (забаненные, неактивные и т.д.).
        """
        await self.emitter.send_log("Получение полного списка друзей для анализа...", "info")
        
        # --- НАЧАЛО ИЗМЕНЕНИЯ ---
        response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,is_closed,deactivated")
        if not response or not response.get('items'):
            await self.emitter.send_log("Не удалось получить список друзей.", "warning")
            return []
        
        all_friends = response.get('items', [])
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        # Сначала отбираем забаненных/удаленных, если включена опция
        banned_friends = []
        if params.filters.remove_banned:
            banned_friends = [f for f in all_friends if f.get('deactivated') in ['banned', 'deleted']]
        
        # Затем работаем с остальными, активными друзьями
        active_friends = [f for f in all_friends if not f.get('deactivated')]
        
        await self.emitter.send_log(f"Найдено забаненных/удаленных: {len(banned_friends)}. Анализ активных друзей...", "info")
        
        # Применяем к активным друзьям остальные фильтры (неактивность, пол и т.д.)
        filtered_active_friends = await apply_filters_to_profiles(active_friends, params.filters)
        
        # Объединяем два списка: сначала "собачки", потом отфильтрованные
        friends_to_remove = banned_friends + filtered_active_friends
        
        return friends_to_remove

    async def remove_friends_by_criteria(self, params: RemoveFriendsRequest):
        return await self._execute_logic(self._remove_friends_by_criteria_logic, params)

    async def _remove_friends_by_criteria_logic(self, params: RemoveFriendsRequest):
        await self.emitter.send_log(f"Начинаем чистку друзей. Цель: удалить до {params.count} чел.", "info")
        stats = await self._get_today_stats()

        # --- ИЗМЕНЕНИЕ: Используем новый метод для получения целей ---
        targets = await self.get_remove_friends_targets(params)
        
        if not targets:
            await self.emitter.send_log("Друзей для удаления по заданным критериям не найдено.", "success")
            return

        # Ограничиваем итоговый список количеством, указанным в задаче
        targets_to_process = targets[:params.count]

        await self.emitter.send_log(f"Всего к удалению: {len(targets_to_process)} чел. Начинаем процесс...", "info")
        processed_count = 0
        
        batch_size = 25
        for i in range(0, len(targets_to_process), batch_size):
            batch = targets_to_process[i:i + batch_size]
            
            calls = [{"method": "friends.delete", "params": {"user_id": friend.get('id')}} for friend in batch]
            
            await self.humanizer.think(action_type='like')
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

# backend/app/services/group_management_service.py

from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.api.schemas.actions import LeaveGroupsRequest, JoinGroupsRequest
from app.core.exceptions import UserLimitReachedError

class GroupManagementService(BaseVKService):

    async def get_leave_groups_targets(self, params: LeaveGroupsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает список сообществ пользователя и фильтрует их по ключевому слову.
        """
        response = await self.vk_api.groups.get(user_id=self.user.vk_id, extended=1)
        if not response or not response.get('items'):
            await self.emitter.send_log("Не удалось получить список сообществ или вы не состоите в группах.", "warning")
            return []
        
        all_groups = [g for g in response['items'] if g.get('type') != 'event']
        
        keyword = (params.filters.status_keyword or "").lower().strip()
        if not keyword:
            return all_groups

        groups_to_leave = [
            group for group in all_groups 
            if keyword in group.get('name', '').lower() or keyword in group.get('activity', '').lower()
        ]

        await self.emitter.send_log(f"Найдено {len(groups_to_leave)} сообществ по ключевому слову '{keyword}'.", "info")
        
        return groups_to_leave

    async def leave_groups_by_criteria(self, params: LeaveGroupsRequest):
        """Публичный метод-обертка для запуска логики выхода из групп."""
        return await self._execute_logic(self._leave_groups_logic, params)

    async def _leave_groups_logic(self, params: LeaveGroupsRequest):
        """Приватный метод, содержащий основную логику выхода из групп."""
        await self.emitter.send_log(f"Запуск задачи: отписаться от {params.count} сообществ.", "info")
        stats = await self._get_today_stats()

        targets = await self.get_leave_groups_targets(params)
        
        if not targets:
            await self.emitter.send_log("Сообществ для отписки по заданным критериям не найдено.", "success")
            return

        targets_to_process = targets[:params.count]
        
        processed_count = 0
        for group in targets_to_process:
            if stats.groups_left_count >= self.user.daily_leave_groups_limit:
                await self.emitter.send_log(f"Достигнут дневной лимит на выход из групп ({self.user.daily_leave_groups_limit}). Задача остановлена.", "warning")
                break 

            group_id, group_name = group['id'], group['name']
            url = f"https://vk.com/club{group_id}"
            
            await self.humanizer.think(action_type='like')
            result = await self.vk_api.groups.leave(group_id)

            if result == 1:
                processed_count += 1
                await self._increment_stat(stats, 'groups_left_count')
                await self.emitter.send_log(f"Вы успешно покинули сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось покинуть сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Покинуто сообществ: {processed_count}.", "success")

    async def get_join_groups_targets(self, params: JoinGroupsRequest) -> List[Dict[str, Any]]:
        keyword = (params.filters.status_keyword or "").strip()
        if not keyword:
            await self.emitter.send_log("Не указано ключевое слово для поиска групп.", "error")
            return []

        search_response = await self.vk_api.groups.search(query=keyword, count=params.count * 2)
        if not search_response or not search_response.get('items'):
            await self.emitter.send_log("Не найдено сообществ по вашему запросу.", "warning")
            return []

        # --- ИСПРАВЛЕНИЕ: Проверяем, не состоит ли пользователь уже в найденных группах ---
        user_groups_response = await self.vk_api.groups.get(user_id=self.user.vk_id, extended=0)
        user_group_ids = set(user_groups_response.get('items', [])) if user_groups_response else set()

        groups_to_join = [
            g for g in search_response['items'] 
            if g['id'] not in user_group_ids and g.get('is_closed', 1) == 0
        ]
        
        return groups_to_join

    async def join_groups_by_criteria(self, params: JoinGroupsRequest):
        return await self._execute_logic(self._join_groups_logic, params)

    async def _join_groups_logic(self, params: JoinGroupsRequest):
        keyword = (params.filters.status_keyword or "").strip()
        await self.emitter.send_log(f"Запуск задачи: вступить в {params.count} сообществ по запросу '{keyword}'.", "info")
        stats = await self._get_today_stats()

        targets = await self.get_join_groups_targets(params)

        if not targets:
            await self.emitter.send_log("Новых открытых сообществ для вступления не найдено.", "success")
            return
        
        targets_to_process = targets[:params.count]
        
        processed_count = 0
        for group in targets_to_process:
            if stats.groups_joined_count >= self.user.daily_join_groups_limit:
                await self.emitter.send_log(f"Достигнут дневной лимит на вступление в группы ({self.user.daily_join_groups_limit}). Задача остановлена.", "warning")
                break 

            group_id, group_name = group['id'], group['name']
            url = f"https://vk.com/club{group_id}"

            await self.humanizer.think(action_type='like')
            result = await self.vk_api.groups.join(group_id)

            if result == 1:
                processed_count += 1
                await self._increment_stat(stats, 'groups_joined_count')
                await self.emitter.send_log(f"Успешное вступление в сообщество: {group_name}", "success", target_url=url)
            else:
                await self.emitter.send_log(f"Не удалось вступить в сообщество {group_name}. Ответ VK: {result}", "error", target_url=url)

        await self.emitter.send_log(f"Задача завершена. Вступлений в сообщества: {processed_count}.", "success")

# --- backend/app\services\humanizer.py ---

import asyncio
import random
import time
import datetime
from typing import Callable, Awaitable
from app.db.models import DelayProfile

DELAY_CONFIG = {
    DelayProfile.fast: {"base": 0.7, "variation": 0.3, "burst_chance": 0.4},
    DelayProfile.normal: {"base": 1.5, "variation": 0.4, "burst_chance": 0.25},
    DelayProfile.slow: {"base": 3.0, "variation": 0.5, "burst_chance": 0.1},
}

class Humanizer:
    def __init__(self, delay_profile: DelayProfile, logger_func: Callable[..., Awaitable[None]]):
        self.profile = DELAY_CONFIG.get(delay_profile, DELAY_CONFIG[DelayProfile.normal])
        self._log = logger_func
        self.session_start_time = time.time()
        self.actions_in_session = 0
        self.burst_actions_left = 0

    def _get_time_of_day_factor(self) -> float:
        """Возвращает множитель в зависимости от времени суток (имитация 'прайм-тайм')."""
        current_hour = datetime.datetime.now().hour
        if 5 <= current_hour < 10: return 1.1  # Утренняя активность
        if 18 <= current_hour < 23: return 1.25 # Вечерний прайм-тайм
        if 1 <= current_hour < 5: return 0.8   # Ночью действия быстрее
        return 1.0

    def _get_fatigue_factor(self) -> float:
        """Чем дольше сессия, тем выше 'усталость' и медленнее действия."""
        minutes_passed = (time.time() - self.session_start_time) / 60
        fatigue = 1.0 + (self.actions_in_session * 0.007) + (minutes_passed * 0.015)
        return min(fatigue, 1.8)

    async def _sleep(self, base_delay: float):
        self.actions_in_session += 1

        if self.burst_actions_left > 0:
            self.burst_actions_left -= 1
            delay = base_delay * random.uniform(0.2, 0.4)
            await asyncio.sleep(delay)
            return

        fatigue = self._get_fatigue_factor()
        time_factor = self._get_time_of_day_factor()
        variation = self.profile["variation"]
        
        delay = base_delay * fatigue * time_factor * random.uniform(1.0 - variation, 1.0 + variation)

        if random.random() < 0.1: # 10% шанс на длинную паузу (отвлекся на чай)
            hesitation = random.uniform(5.0, 12.0)
            await self._log(f"Имитация отвлечения на {hesitation:.1f} сек.", "debug")
            delay += hesitation

        await self._log(f"Пауза ~{delay:.1f}с (усталость:x{fatigue:.2f}, время:x{time_factor:.2f})", "debug")
        await asyncio.sleep(delay)

    async def think(self, action_type: str):
        """Имитация 'обдумывания' действия перед его выполнением."""
        base_thinking_time = self.profile['base']
        if action_type == 'message': base_thinking_time *= 1.8
        if action_type == 'add_friend': base_thinking_time *= 1.5
        await self._sleep(base_thinking_time)

    async def read_and_scroll(self):
        """Имитация загрузки, скроллинга и чтения контента."""
        await self._sleep(self.profile['base'] * 1.2) # "Загрузка"
        
        scroll_count = random.choices([0, 1, 2, 3, 4], weights=[20, 30, 30, 15, 5], k=1)[0]
        if scroll_count > 0:
            for _ in range(scroll_count):
                await self._sleep(self.profile['base'] * 0.7)
        
        if random.random() < self.profile["burst_chance"]:
            self.burst_actions_left = random.randint(3, 8)
            await self._log(f"Начало 'пакетного' режима на {self.burst_actions_left} действий.", "debug")

# --- backend/app\services\incoming_request_service.py ---

# --- backend/app/services/incoming_request_service.py ---
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AcceptFriendsRequest

class IncomingRequestService(BaseVKService):

    async def get_accept_friends_targets(self, params: AcceptFriendsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает и фильтрует входящие заявки в друзья.
        """
        response = await self.vk_api.get_incoming_friend_requests(extended=1)
        if not response or not response.get('items'):
            await self.emitter.send_log("Входящие заявки не найдены.", "info")
            return []
        
        profiles = response.get('items', [])
        await self.emitter.send_log(f"Найдено {len(profiles)} заявок. Начинаем фильтрацию...", "info")
        
        filtered_profiles = await apply_filters_to_profiles(profiles, params.filters)
        return filtered_profiles

    async def accept_friend_requests(self, params: AcceptFriendsRequest):
        return await self._execute_logic(self._accept_friend_requests_logic, params)

    async def _accept_friend_requests_logic(self, params: AcceptFriendsRequest):
        await self.emitter.send_log("Начинаем прием заявок в друзья...", "info")
        stats = await self._get_today_stats()
        
        # ШАГ 1: Получаем цели
        targets = await self.get_accept_friends_targets(params)

        await self.emitter.send_log(f"После фильтрации осталось: {len(targets)}.", "info")
        
        if not targets:
            await self.emitter.send_log("Подходящих заявок для приема не найдено.", "success")
            return
        
        processed_count = 0
        batch_size = 25
        for i in range(0, len(targets), batch_size):
            batch = targets[i:i + batch_size]
            calls = [{"method": "friends.add", "params": {"user_id": p.get('id')}} for p in batch]

            await self.humanizer.think(action_type='add_friend')
            results = await self.vk_api.execute(calls)

            if results is None:
                await self.emitter.send_log("Пакетный запрос на принятие заявок не удался.", "error")
                continue

            for profile, result in zip(batch, results):
                user_id = profile.get('id')
                name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"
                
                if result in [1, 2, 4]:
                    processed_count += 1
                    await self._increment_stat(stats, 'friend_requests_accepted_count')
                    await self.emitter.send_log(f"Принята заявка от {name}", "success", target_url=url)
                else:
                    error_msg = result.get('error_msg', f'неизвестная ошибка, код {result}') if isinstance(result, dict) else f'код {result}'
                    await self.emitter.send_log(f"Не удалось принять заявку от {name}. Ответ VK: {error_msg}", "error", target_url=url)

        await self.emitter.send_log(f"Завершено. Принято заявок: {processed_count}.", "success")

# --- backend/app\services\message_humanizer.py ---

# --- backend/app/services/message_humanizer.py ---
import asyncio
import random
import structlog
from typing import List, Dict, Any, Literal, Optional
from app.services.vk_api import VKAPI, VKAccessDeniedError
from app.services.event_emitter import RedisEventEmitter

log = structlog.get_logger(__name__)

# Настройки скоростей "печати" (символов в минуту) и вариативности
SPEED_PROFILES = {
    "slow": {"cpm": 300, "variation": 0.3, "base_delay": 2.5},
    "normal": {"cpm": 600, "variation": 0.25, "base_delay": 1.5},
    "fast": {"cpm": 900, "variation": 0.2, "base_delay": 0.8},
}

SpeedProfile = Literal["slow", "normal", "fast"]

class MessageHumanizer:
    """
    Обеспечивает последовательную отправку сообщений с имитацией
    человеческого поведения: задержками, "прочтением" диалога и "набором" текста.
    """
    def __init__(self, vk_api: VKAPI, emitter: RedisEventEmitter):
        self.vk_api = vk_api
        self.emitter = emitter

    async def send_messages_sequentially(
        self,
        targets: List[Dict[str, Any]],
        message_template: str,
        attachments: Optional[str] = None, # <-- ИЗМЕНЕНИЕ: Принимает готовую строку вложений
        speed: SpeedProfile = "normal",
        simulate_typing: bool = True
    ) -> int:
        """
        Отправляет сообщения каждому получателю из списка по очереди.

        :param targets: Список словарей с информацией о получателях.
        :param message_template: Шаблон сообщения, поддерживает {name}.
        :param attachments: Строка с ID вложений (напр. 'photo123_456,photo123_789').
        :param speed: Профиль скорости отправки.
        :param simulate_typing: Включать ли имитацию набора текста.
        :return: Количество успешно отправленных сообщений.
        """
        profile = SPEED_PROFILES.get(speed, SPEED_PROFILES["normal"])
        successful_sends = 0

        for target in targets:
            target_id = target.get('id')
            if not target_id:
                continue

            first_name = target.get('first_name', '')
            full_name = f"{first_name} {target.get('last_name', '')}"
            url = f"https://vk.com/id{target_id}"
            
            final_message = message_template.replace("{name}", first_name)
            
            try:
                # 1. Имитация "открытия и прочтения" диалога
                # --- ИСПРАВЛЕНИЕ: Удалена строка `await self.vk_api.messages.markAsRead(peer_id=target_id)`, вызывавшая ошибку ---
                await asyncio.sleep(random.uniform(0.5, 1.2))

                # 2. Расчет задержки и имитация набора текста
                if simulate_typing:
                    typing_duration = (len(final_message) / (profile["cpm"] / 60)) 
                    variation = profile["variation"]
                    total_delay = typing_duration * random.uniform(1 - variation, 1 + variation)
                    
                    await asyncio.sleep(profile["base_delay"] * random.uniform(0.8, 1.2))
                    
                    await self.emitter.send_log(f"Имитация набора текста для {full_name} (~{total_delay:.1f} сек)...", "debug")
                    await self.vk_api.messages.setActivity(user_id=target_id, type='typing')
                    await asyncio.sleep(total_delay)

                # 3. Отправка сообщения с вложениями
                if await self.vk_api.messages.send(target_id, final_message, attachment=attachments):
                    successful_sends += 1
                    await self.emitter.send_log(f"Сообщение для {full_name} успешно отправлено.", "success", target_url=url)
                else:
                    await self.emitter.send_log(f"Не удалось отправить сообщение для {full_name}.", "error", target_url=url)

            except VKAccessDeniedError:
                await self.emitter.send_log(f"Не удалось отправить (профиль закрыт или ЧС): {full_name}", "warning", target_url=url)
            except Exception as e:
                log.error("message_humanizer.error", user_id=self.emitter.user_id, error=str(e))
                await self.emitter.send_log(f"Ошибка при отправке сообщения для {full_name}: {e}", "error", target_url=url)
            
            # 4. Финальная задержка перед переходом к следующему диалогу
            await asyncio.sleep(profile["base_delay"] * random.uniform(1.5, 2.5))

        return successful_sends

# --- backend/app\services\message_service.py ---

# --- backend/app/services/message_service.py ---
import random
from typing import List, Dict, Any
from app.services.base import BaseVKService
from app.core.exceptions import InvalidActionSettingsError, UserLimitReachedError
from app.services.vk_api import VKAccessDeniedError
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import MassMessagingRequest
from app.services.message_humanizer import MessageHumanizer


class MessageService(BaseVKService):

    async def filter_targets_by_conversation_status(
        self,
        targets: List[Dict[str, Any]],
        only_new_dialogs: bool,
        only_unread: bool
    ) -> List[Dict[str, Any]]:
        """
        Фильтрует список целей на основе статуса их диалога с пользователем.
        """
        if only_new_dialogs and only_unread:
            raise InvalidActionSettingsError("Нельзя одновременно использовать 'Только новые диалоги' и 'Только непрочитанные'.")

        final_targets = list(targets) 

        if only_new_dialogs:
            await self.emitter.send_log("Применяем фильтр: 'Только новые диалоги'...", "info")
            dialogs = await self.vk_api.get_conversations(count=200)
            dialog_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in dialogs.get('items', [])}
            final_targets = [t for t in targets if t.get('id') not in dialog_peer_ids]

        if only_unread:
            await self.emitter.send_log("Применяем фильтр: 'Только непрочитанные'...", "info")
            unread_convs = await self.vk_api.get_conversations(count=200, filter='unread')
            if not unread_convs or not unread_convs.get('items'):
                return []
            unread_peer_ids = {conv.get('conversation', {}).get('peer', {}).get('id') for conv in unread_convs.get('items', [])}
            final_targets = [t for t in targets if t.get('id') in unread_peer_ids]
            
        return final_targets

    async def get_mass_messaging_targets(self, params: MassMessagingRequest) -> List[Dict[str, Any]]:
        """Вспомогательный метод для получения и фильтрации целей для МАССОВОЙ РАССЫЛКИ."""
        # <<< ИСПРАВЛЕНИЕ ЗДЕСЬ >>>
        response = await self.vk_api.get_user_friends(self.user.vk_id, fields="sex,online,last_seen,status,is_closed,city")
        
        if not response or not response.get('items'):
            return []
        
        # Итерируемся по response.get('items', []), а не по всему ответу
        friends_list = [f for f in response.get('items', []) if f.get('id') != self.user.vk_id]

        filtered_friends = await apply_filters_to_profiles(friends_list, params.filters)
        
        targets = await self.filter_targets_by_conversation_status(
            filtered_friends, params.only_new_dialogs, params.only_unread
        )
            
        return targets

    async def send_mass_message(self, params: MassMessagingRequest):
         return await self._execute_logic(self._send_mass_message_logic, params)

    async def _send_mass_message_logic(self, params: MassMessagingRequest):
        if not params.message_text or not params.message_text.strip():
            raise InvalidActionSettingsError("Текст сообщения не может быть пустым.")
        
        attachments_str = ",".join(params.attachments) if params.attachments else None

        await self.emitter.send_log(f"Запуск массовой рассылки. Цель: {params.count} сообщений.", "info")
        stats = await self._get_today_stats()
        if self.user.daily_message_limit <= 0:
            raise UserLimitReachedError(f"Достигнут дневной лимит сообщений ({self.user.daily_message_limit}).")

        target_friends = await self.get_mass_messaging_targets(params)

        if not target_friends:
            await self.emitter.send_log("Не найдено подходящих получателей по заданным фильтрам.", "success")
            return
            
        await self.emitter.send_log(f"Найдено получателей по фильтрам: {len(target_friends)}. Начинаем отправку.", "info")
        random.shuffle(target_friends)
        
        targets_to_process = target_friends[:params.count]
        processed_count = 0
        
        if params.humanized_sending.enabled:
            await self.emitter.send_log("Активирован режим 'человечной' отправки.", "info")
            humanizer = MessageHumanizer(self.vk_api, self.emitter)
            
            for target in targets_to_process:
                # Вторичная проверка внутри цикла на случай, если лимит закончился во время работы
                if stats.messages_sent_count >= self.user.daily_message_limit:
                    await self.emitter.send_log(f"Дневной лимит сообщений ({self.user.daily_message_limit}) был достигнут во время рассылки.", "warning")
                    break # Выходим из цикла, а не бросаем ошибку
                
                sent_count = await humanizer.send_messages_sequentially(
                    targets=[target],
                    message_template=params.message_text,
                    attachments=attachments_str,
                    speed=params.humanized_sending.speed,
                    simulate_typing=params.humanized_sending.simulate_typing
                )
                if sent_count > 0:
                    processed_count += 1
                    await self._increment_stat(stats, 'messages_sent_count')

        else: # Быстрая пакетная отправка
            for friend in targets_to_process:
                if stats.messages_sent_count >= self.user.daily_message_limit:
                    await self.emitter.send_log(f"Дневной лимит сообщений ({self.user.daily_message_limit}) был достигнут во время рассылки.", "warning")
                    break

                friend_id = friend.get('id')
                name = f"{friend.get('first_name', '')} {friend.get('last_name', '')}"
                url = f"https://vk.com/id{friend_id}"
                
                final_message = params.message_text.replace("{name}", friend.get('first_name', ''))
                await self.humanizer.think(action_type='message')

                try:
                    if await self.vk_api.messages.send(friend_id, final_message, attachment=attachments_str):
                        processed_count += 1
                        await self._increment_stat(stats, 'messages_sent_count')
                        await self.emitter.send_log(f"Сообщение для {name} успешно отправлено.", "success", target_url=url)
                except VKAccessDeniedError:
                    await self.emitter.send_log(f"Не удалось отправить (профиль закрыт или ЧС): {name}", "warning", target_url=url)
        
        await self.emitter.send_log(f"Рассылка завершена. Отправлено сообщений: {processed_count}.", "success")

# --- backend/app\services\outgoing_request_service.py ---

# backend/app/services/outgoing_request_service.py
from typing import Dict, Any, List
from app.services.base import BaseVKService
from app.db.models import DailyStats, FriendRequestLog
from sqlalchemy.dialects.postgresql import insert
from app.core.exceptions import UserLimitReachedError
from app.core.config import settings
from redis.asyncio import Redis as AsyncRedis
from app.services.vk_user_filter import apply_filters_to_profiles
from app.api.schemas.actions import AddFriendsRequest, LikeAfterAddConfig

class OutgoingRequestService(BaseVKService):

    async def get_add_recommended_targets(self, params: AddFriendsRequest) -> List[Dict[str, Any]]:
        """
        ПОИСК ЦЕЛЕЙ: Получает и фильтрует пользователей из рекомендаций.
        """
        await self._initialize_vk_api()
        # Берем с запасом, т.к. фильтрация может отсеять многих
        response = await self.vk_api.get_recommended_friends(count=params.count * 3)
        
        # <<< ИСПРАВЛЕНИЕ ЗДЕСЬ >>>
        if not response or not response.get('items'):
            await self.emitter.send_log("Рекомендации не найдены.", "warning")
            return []

        await self.emitter.send_log(f"Найдено {len(response.get('items', []))} рекомендаций. Применяем фильтры...", "info")
        
        # Итерируемся по response.get('items', [])
        filtered_profiles = await apply_filters_to_profiles(response.get('items', []), params.filters)
        # <<< КОНЕЦ ИСПРАВЛЕНИЯ >>>
        
        return filtered_profiles

    async def add_recommended_friends(self, params: AddFriendsRequest):
        return await self._execute_logic(self._add_recommended_friends_logic, params)

    async def _add_recommended_friends_logic(self, params: AddFriendsRequest):
        await self.emitter.send_log(f"Начинаем добавление до {params.count} друзей из рекомендаций...", "info")
        stats = await self._get_today_stats()

        targets = await self.get_add_recommended_targets(params)
        
        await self.emitter.send_log(f"После фильтрации осталось: {len(targets)}. Начинаем отправку заявок.", "info")

        if not targets:
            await self.emitter.send_log("Подходящих пользователей для добавления не найдено.", "success")
            return "Подходящих пользователей для добавления не найдено."

        final_results = []
        redis_lock_client = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
        try:
            processed_count = 0
            for profile in targets:
                if processed_count >= params.count: break
                if stats.friends_added_count >= self.user.daily_add_friends_limit:
                    raise UserLimitReachedError(f"Достигнут дневной лимит на отправку заявок ({self.user.daily_add_friends_limit}).")
                
                user_id = profile.get('id')
                if not user_id: continue
                
                lock_key = f"lock:add_friend:{self.user.id}:{user_id}"
                if not await redis_lock_client.set(lock_key, "1", ex=3600, nx=True):
                    continue

                await self.humanizer.think(action_type='add_friend')
                
                message = None
                if params.send_message_on_add and params.message_text:
                    # Проверяем лимит сообщений ПЕРЕД тем, как сформировать сообщение
                    if stats.messages_sent_count < self.user.daily_message_limit:
                        message = params.message_text.replace("{name}", profile.get("first_name", ""))
                    else:
                        await self.emitter.send_log(f"Достигнут лимит сообщений. Заявка для {profile.get('first_name')} будет отправлена без приветствия.", "warning")

                result = await self.vk_api.add_friend(user_id, message) 
                
                name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}"
                url = f"https://vk.com/id{user_id}"
                
                if result in [1, 2, 4]:
                    processed_count += 1
                    await self._increment_stat(stats, 'friends_added_count')
                    
                    # Если сообщение было успешно отправлено вместе с заявкой, учитываем его в лимите
                    if message:
                        await self._increment_stat(stats, 'messages_sent_count')

                    log_stmt = insert(FriendRequestLog).values(user_id=self.user.id, target_vk_id=user_id).on_conflict_do_nothing()
                    await self.db.execute(log_stmt)

                    log_msg = f"Отправлена заявка пользователю {name}"
                    if message:
                        log_msg += " с сообщением."
                    await self.emitter.send_log(log_msg, "success", target_url=url)
                    final_results.append(log_msg)
                    
                    if params.like_config.enabled:
                        if not profile.get('is_closed', True):
                            like_results = await self._like_user_content(user_id, profile, params.like_config, stats)
                            final_results.extend(like_results)
                        else:
                            await self.emitter.send_log(f"Профиль {name} закрыт, пропуск лайкинга.", "info", target_url=url)
                else:
                    await self.emitter.send_log(f"Не удалось отправить заявку {name}. Ответ VK: {result}", "error", target_url=url)
                    await redis_lock_client.delete(lock_key)
            
            summary_message = f"Завершено. Отправлено заявок: {processed_count}."
            await self.emitter.send_log(summary_message, "success")
            final_results.append(summary_message)
            
            return " ".join(final_results)

        finally:
            await redis_lock_client.close()

    async def _like_user_content(self, user_id: int, profile: Dict[str, Any], config: LikeAfterAddConfig, stats: DailyStats) -> list[str]:
        # ... (код без изменений)
        like_results = []
        if stats.likes_count >= self.user.daily_likes_limit:
            await self.emitter.send_log("Достигнут дневной лимит лайков, пропуск лайкинга после добавления.", "warning")
            return like_results

        if 'avatar' in config.targets and profile.get('photo_id'):
            photo_id_parts = profile.get('photo_id', '').split('_')
            if len(photo_id_parts) == 2:
                photo_id = int(photo_id_parts[1])
                await self.humanizer.think(action_type='like')
                if await self.vk_api.add_like('photo', user_id, photo_id):
                    await self._increment_stat(stats, 'likes_count')
                    log_msg = f"Поставлен лайк на аватар."
                    await self.emitter.send_log(log_msg, "success", target_url=f"https://vk.com/photo{user_id}_{photo_id}")
                    like_results.append(log_msg)

        if 'wall' in config.targets:
            wall = await self.vk_api.get_wall(owner_id=user_id, count=1)
            if wall and wall.get('items') and stats.likes_count < self.user.daily_likes_limit:
                post = wall['items'][0]
                await self.humanizer.think(action_type='like')
                if await self.vk_api.add_like('post', user_id, post.get('id')):
                    await self._increment_stat(stats, 'likes_count')
                    log_msg = f"Поставлен лайк на пост на стене."
                    await self.emitter.send_log(log_msg, "success", target_url=f"https://vk.com/wall{user_id}_{post.get('id')}")
                    like_results.append(log_msg)
        
        return like_results

# --- backend/app\services\profile_analytics_service.py ---

# --- ЗАМЕНИТЬ ВЕСЬ ФАЙЛ ---
import datetime
from sqlalchemy.dialects.postgresql import insert
from app.services.base import BaseVKService
from app.db.models import ProfileMetric
from app.services.vk_api import VKAPIError
import structlog

log = structlog.get_logger(__name__)

class ProfileAnalyticsService(BaseVKService):

    async def snapshot_profile_metrics(self):
        """
        Собирает ключевые метрики профиля, включая ВСЕ и НЕДАВНИЕ лайки (раздельно),
        и сохраняет их в БД как "снимок" за текущий день.
        """
        try:
            await self._initialize_vk_api()
        except Exception as e:
            log.error("snapshot_metrics.init_failed", user_id=self.user.id, error=str(e))
            return

        # 1. Получаем счетчики
        user_info_list = await self.vk_api.users.get(user_ids=str(self.user.vk_id), fields="counters")
        counters = user_info_list[0].get('counters', {}) if user_info_list else {}
        wall_info = await self.vk_api.wall.get(owner_id=self.user.vk_id, count=0)
        wall_posts_count = wall_info.get('count', 0) if wall_info else 0

        # 2. <<< ИЗМЕНЕНО: Используем пользовательские настройки >>>
        recent_posts_to_check = self.user.analytics_settings_posts_count
        recent_photos_to_check = self.user.analytics_settings_photos_count
        
        # 3. Считаем лайки
        recent_post_likes, total_post_likes = await self._get_likes_from_wall(wall_posts_count, recent_posts_to_check)
        recent_photo_likes, total_photo_likes = await self._get_likes_from_photos(counters.get('photos', 0), recent_photos_to_check)

        # 4. Сохраняем все в БД
        today = datetime.date.today()
        stmt = insert(ProfileMetric).values(
            user_id=self.user.id, date=today,
            friends_count=counters.get('friends', 0),
            followers_count=counters.get('followers', 0),
            photos_count=counters.get('photos', 0),
            wall_posts_count=wall_posts_count,
            recent_post_likes=recent_post_likes,
            recent_photo_likes=recent_photo_likes,
            total_post_likes=total_post_likes,
            total_photo_likes=total_photo_likes,
        ).on_conflict_do_update(
            index_elements=['user_id', 'date'],
            set_={
                'friends_count': counters.get('friends', 0), 'followers_count': counters.get('followers', 0),
                'photos_count': counters.get('photos', 0), 'wall_posts_count': wall_posts_count,
                'recent_post_likes': recent_post_likes, 'recent_photo_likes': recent_photo_likes,
                'total_post_likes': total_post_likes, 'total_photo_likes': total_photo_likes,
            }
        )
        await self.db.execute(stmt)
        log.info("snapshot_metrics.success", user_id=self.user.id, total_post_likes=total_post_likes, total_photo_likes=total_photo_likes)

    async def _get_likes_from_wall(self, total_count: int, recent_count: int) -> tuple[int, int]:
        if total_count == 0:
            return 0, 0
        
        total_likes = 0
        recent_likes = 0
        offset = 0
        is_first_chunk = True
        
        while offset < total_count:
            try:
                chunk = await self.vk_api.wall.get(owner_id=self.user.vk_id, count=100, offset=offset)
                if not chunk or not chunk.get('items'):
                    break
                
                chunk_likes = sum(p.get('likes', {}).get('count', 0) for p in chunk['items'])
                total_likes += chunk_likes
                
                if is_first_chunk:
                    # Лайки с первой страницы всегда считаются "недавними" (до recent_count)
                    recent_items = chunk['items'][:recent_count]
                    recent_likes = sum(p.get('likes', {}).get('count', 0) for p in recent_items)
                    is_first_chunk = False

                offset += 100
            except VKAPIError as e:
                log.warn("snapshot.wall_likes_error", user_id=self.user.id, error=str(e))
                break
        return recent_likes, total_likes

    async def _get_likes_from_photos(self, total_count: int, recent_count: int) -> tuple[int, int]:
        if total_count == 0:
            return 0, 0

        total_likes = 0
        recent_likes = 0
        offset = 0
        is_first_chunk = True

        while offset < total_count:
            try:
                chunk = await self.vk_api.photos.getAll(owner_id=self.user.vk_id, count=200, offset=offset)
                if not chunk or not chunk.get('items'):
                    break
                
                chunk_likes = sum(p.get('likes', {}).get('count', 0) for p in chunk['items'])
                total_likes += chunk_likes

                if is_first_chunk:
                    recent_items = chunk['items'][:recent_count]
                    recent_likes = sum(p.get('likes', {}).get('count', 0) for p in recent_items)
                    is_first_chunk = False

                offset += 200
            except VKAPIError as e:
                log.warn("snapshot.photo_likes_error", user_id=self.user.id, error=str(e))
                break
        return recent_likes, total_likes

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
            user_info_list = await self.vk_api.users.get(user_ids=str(self.user.vk_id), fields="counters")
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
        await self.humanizer.read_and_scroll()
        await self.emitter.send_log("Начинаем просмотр историй...", "info")
        stats = await self._get_today_stats()

        response = await self.vk_api.stories.get()
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

# --- backend/app\services\vk_user_filter.py ---

# backend/app/services/vk_user_filter.py

import datetime
from typing import Dict, Any, List

from app.api.schemas.actions import ActionFilters


async def apply_filters_to_profiles(
    profiles: List[Dict[str, Any]],
    filters: ActionFilters,
) -> List[Dict[str, Any]]:
    """
    Применяет различные фильтры к списку профилей VK.

    Эта функция является "чистой" и не делает внешних запросов к API.
    Она работает с уже полученными данными профилей.

    Args:
        profiles: Список словарей, где каждый словарь - это профиль пользователя VK.
        filters: Pydantic-модель с параметрами для фильтрации.

    Returns:
        Отфильтрованный список профилей.
    """
    filtered_profiles = []
    # Получаем текущее время один раз для эффективности
    now_ts = datetime.datetime.now(datetime.UTC).timestamp()

    for profile in profiles:
        # --- Обработка деактивированных ("забаненных", "удаленных") профилей ---
        deactivated_status = profile.get('deactivated')
        if deactivated_status:
            # Если у профиля есть статус (banned/deleted) и фильтр `remove_banned`
            # НЕ установлен в True, то мы пропускаем такой профиль.
            # Это позволяет включать "собачек" в выборку только для задач
            # по чистке, где этот флаг намеренно выставляется.
            if not filters.remove_banned:
                continue

        # --- Стандартные фильтры, исключающие профиль из выборки ---

        # Фильтр по полу (0 - любой пол, поэтому проверяем только если 1 или 2)
        if filters.sex and profile.get('sex') != filters.sex:
            continue

        # Фильтр по статусу "онлайн"
        if filters.is_online and not profile.get('online', 0):
            continue

        # Фильтр по последнему визиту
        last_seen_ts = profile.get('last_seen', {}).get('time', 0)
        if last_seen_ts > 0:  # Проверяем только если дата визита известна
            hours_since_seen = (now_ts - last_seen_ts) / 3600

            # **ЛОГИКА ДЛЯ УДАЛЕНИЯ НЕАКТИВНЫХ**
            # Если фильтр `last_seen_days` активен, мы хотим удалить тех,
            # кто НЕ заходил N дней. Значит, мы должны ПРОПУСТИТЬ тех,
            # кто заходил НЕДАВНО (меньше или равно N дней назад).
            if filters.last_seen_days and hours_since_seen <= (filters.last_seen_days * 24):
                continue

            # **ЛОГИКА ДЛЯ ДОБАВЛЕНИЯ АКТИВНЫХ**
            # Если фильтр `last_seen_hours` активен, мы хотим добавить тех,
            # кто заходил в течение N часов. Значит, мы должны ПРОПУСТИТЬ тех,
            # кто НЕ заходил БОЛЬШЕ N часов.
            if filters.last_seen_hours and hours_since_seen > filters.last_seen_hours:
                continue

        elif filters.last_seen_days or filters.last_seen_hours:
            # Если фильтр по дате есть, а у профиля даты нет, то пропускаем его
            continue

        # Фильтр по ключевому слову в статусе
        status_keyword = (filters.status_keyword or "").lower().strip()
        if status_keyword and status_keyword not in profile.get('status', '').lower():
            continue

        # Фильтр по городу
        city_filter = (filters.city or "").lower().strip()
        if city_filter and city_filter not in profile.get('city', {}).get('title', '').lower():
            continue

        # Фильтр для лайков в ленте: только посты с фото
        if filters.only_with_photo and not profile.get('photo_id'):
            continue

        # Если профиль прошел все проверки, добавляем его в итоговый список
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



# --- backend/app\services\vk_api\account.py ---

#backend/app/services/vk_api/account.py

from typing import Optional
from .base import BaseVKSection

class AccountAPI(BaseVKSection):
    async def setOnline(self) -> Optional[int]:
        return await self._make_request("account.setOnline")

# --- backend/app\services\vk_api\base.py ---

import aiohttp
import asyncio

# --- ИСКЛЮЧЕНИЯ ---
class VKAPIError(Exception):
    def __init__(self, message: str, error_code: int):
        self.message = message
        self.error_code = error_code
        super().__init__(f"VK API Error [{self.error_code}]: {self.message}")

class VKAuthError(VKAPIError): pass
class VKRateLimitError(VKAPIError): pass
class VKAccessDeniedError(VKAPIError): pass
class VKFloodControlError(VKAPIError): pass
class VKCaptchaError(VKAPIError): pass
class VKTooManyRequestsError(VKAPIError): pass

ERROR_CODE_MAP = {
    5: VKAuthError, 6: VKRateLimitError, 9: VKFloodControlError, 14: VKCaptchaError,
    15: VKAccessDeniedError, 18: VKAccessDeniedError, 29: VKTooManyRequestsError,
    203: VKAccessDeniedError, 902: VKAccessDeniedError,
}

# --- БАЗОВЫЙ КЛАСС ДЛЯ РАЗДЕЛОВ ---
class BaseVKSection:
    def __init__(self, request_method: callable):
        self._make_request = request_method

# --- backend/app\services\vk_api\friends.py ---


#backend/app/services/vk_api/friends.py

from typing import Optional, Dict, Any
from .base import BaseVKSection

class FriendsAPI(BaseVKSection):
    async def get(self, user_id: int, fields: str, order: str = "random") -> Optional[Dict[str, Any]]:
        params = {"user_id": user_id, "fields": fields, "order": order}
        response = await self._make_request("friends.get", params=params)
        if not response or "items" not in response:
            return None
        # Возвращаем полный ответ, т.к. он содержит `count`
        return response

    async def getRequests(self, count: int = 1000, extended: int = 0, **kwargs) -> Optional[Dict[str, Any]]:
        params = {"count": count, "extended": extended, **kwargs}
        if extended == 1:
            params['fields'] = "sex,online,last_seen,is_closed,status,counters"
        return await self._make_request("friends.getRequests", params=params)

    async def getSuggestions(self, count: int = 200, fields: str = "sex,online,last_seen,is_closed,status,counters,photo_id") -> Optional[Dict[str, Any]]:
        params = {"filter": "mutual", "count": count, "fields": fields}
        return await self._make_request("friends.getSuggestions", params)

    async def add(self, user_id: int, text: Optional[str] = None) -> Optional[int]:
        params = {"user_id": user_id}
        if text: params["text"] = text
        return await self._make_request("friends.add", params=params)

    async def delete(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self._make_request("friends.delete", params={"user_id": user_id})

# --- backend/app\services\vk_api\groups.py ---

from typing import Optional, Dict, Any
from .base import BaseVKSection

class GroupsAPI(BaseVKSection):
    async def get(self, user_id: int, extended: int = 1, fields: str = "members_count", count: int = 1000) -> Optional[Dict[str, Any]]:
        params = {"user_id": user_id, "extended": extended, "fields": fields, "count": count}
        return await self._make_request("groups.get", params=params)

    async def leave(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.leave", params={"group_id": group_id})

    async def search(self, query: str, count: int = 100, sort: int = 6) -> Optional[Dict[str, Any]]:
        return await self._make_request("groups.search", params={"q": query, "count": count, "sort": sort})

    async def join(self, group_id: int) -> Optional[int]:
        return await self._make_request("groups.join", params={"group_id": group_id})

# --- backend/app\services\vk_api\likes.py ---

from typing import Optional, Dict, Any
from .base import BaseVKSection

class LikesAPI(BaseVKSection):
    async def add(self, item_type: str, owner_id: int, item_id: int) -> Optional[Dict[str, Any]]:
        params = {"type": item_type, "owner_id": owner_id, "item_id": item_id}
        return await self._make_request("likes.add", params=params)

# --- backend/app\services\vk_api\messages.py ---

import random
from typing import Optional, Dict, Any, Literal
from .base import BaseVKSection

class MessagesAPI(BaseVKSection):
    async def send(self, user_id: int, message: str, attachment: Optional[str] = None) -> Optional[int]:
        params = {
            "user_id": user_id,
            "message": message,
            "random_id": random.randint(0, 2**31)
        }
        # --- ДОБАВЛЕНО ---
        if attachment:
            params["attachment"] = attachment
        # -----------------
        return await self._make_request("messages.send", params=params)

    async def getConversations(self, count: int = 200, filter: Optional[Literal['all', 'unread', 'important', 'unanswered']] = 'all') -> Optional[Dict[str, Any]]:
        params = {"count": count, "filter": filter}
        return await self._make_request("messages.getConversations", params=params)
    
    async def markAsRead(self, peer_id: int) -> Optional[int]:
        """Отмечает сообщения как прочитанные."""
        params = {"peer_id": peer_id}
        return await self._make_request("messages.markAsRead", params=params)

    # НОВЫЙ МЕТОД:
    async def setActivity(self, user_id: int, type: str = 'typing') -> Optional[int]:
        """Показывает статус 'набирает сообщение'."""
        params = {"user_id": user_id, "type": type}
        return await self._make_request("messages.setActivity", params=params)

# --- backend/app\services\vk_api\newsfeed.py ---

from typing import Optional, Dict, Any
from .base import BaseVKSection

class NewsfeedAPI(BaseVKSection):
    async def get(self, count: int, filters: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает список новостей для текущего пользователя.
        https://dev.vk.com/method/newsfeed.get
        """
        params = {"count": count, "filters": filters}
        return await self._make_request("newsfeed.get", params=params)

# --- backend/app\services\vk_api\photos.py ---

# --- backend/app/services/vk_api/photos.py ---

import json # <--- ДОБАВЛЕН ИМПОРТ
from typing import Optional, Dict, Any
from .base import BaseVKSection
import aiohttp

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from . import VKAPI

class PhotosAPI(BaseVKSection):
    def __init__(self, request_method: callable, vk_api_client: 'VKAPI'):
        super().__init__(request_method)
        self._vk_api_client = vk_api_client

    async def getAll(self, owner_id: int, count: int = 200) -> Optional[Dict[str, Any]]:
        params = {"owner_id": owner_id, "count": count, "extended": 1}
        return await self._make_request("photos.getAll", params=params)

    async def getWallUploadServer(self) -> Optional[Dict[str, Any]]:
        return await self._make_request('photos.getWallUploadServer')

    async def saveWallPhoto(self, upload_data: dict) -> Optional[Dict[str, Any]]:
        if 'photo' in upload_data and not isinstance(upload_data['photo'], str):
            upload_data['photo'] = json.dumps(upload_data['photo'], ensure_ascii=False)
        return await self._make_request('photos.saveWallPhoto', params=upload_data)
        
    async def upload_for_wall(self, photo_data: bytes) -> Optional[str]:
        upload_server = await self.getWallUploadServer()
        if not upload_server or 'upload_url' not in upload_server:
            return None
        
        form = aiohttp.FormData()
        form.add_field('photo', photo_data, filename='photo.jpg', content_type='image/jpeg')
        
        session = await self._vk_api_client._get_session()
        timeout = aiohttp.ClientTimeout(total=45)
        
        # Оборачиваем в try-except для лучшего логгирования ошибки
        try:
            async with session.post(upload_server['upload_url'], data=form, proxy=self._vk_api_client.proxy, timeout=timeout) as resp:
                resp.raise_for_status()
                # VK может вернуть text/plain, поэтому явно указываем content_type=None
                upload_result = await resp.json(content_type=None)
        except Exception as e:
            # Если ошибка на этом этапе, мы будем знать точно, где она
            print(f"ОШИБКА при загрузке на сервер VK: {e}")
            raise

        if not all(k in upload_result for k in ['server', 'photo', 'hash']):
             return None

        saved_photo_list = await self.saveWallPhoto(upload_data=upload_result)
        if not saved_photo_list or not saved_photo_list[0]:
            return None
        
        photo = saved_photo_list[0]
        return f"photo{photo['owner_id']}_{photo['id']}"

# --- backend/app\services\vk_api\stories.py ---

from typing import Optional, Dict, Any
from .base import BaseVKSection

class StoriesAPI(BaseVKSection):
    async def get(self) -> Optional[Dict[str, Any]]:
        return await self._make_request("stories.get", params={})

# --- backend/app\services\vk_api\users.py ---

# backend/app/services/vk_api/users.py

from typing import Optional, Any
from .base import BaseVKSection

class UsersAPI(BaseVKSection):
    async def get(self, user_ids: Optional[str] = None, fields: Optional[str] = "photo_200,sex,online,last_seen,is_closed,status,counters,photo_id") -> Optional[Any]:
        params = {'fields': fields}
        if user_ids:
            params['user_ids'] = user_ids
        response = await self._make_request("users.get", params=params)
        
        if response and isinstance(response, list):
            return response

            
        return None

# --- backend/app\services\vk_api\wall.py ---

# backend/app/services/vk_api/wall.py

from typing import Optional, Dict, Any
from .base import BaseVKSection

class WallAPI(BaseVKSection):
    async def get(self, owner_id: int, count: int = 5) -> Optional[Dict[str, Any]]:
        return await self._make_request("wall.get", params={"owner_id": owner_id, "count": count})

    async def post(self, owner_id: int, message: str, attachments: str) -> Optional[Dict[str, Any]]:
        params = {"owner_id": owner_id, "from_group": 0, "message": message, "attachments": attachments}
        return await self._make_request("wall.post", params=params)

    async def delete(self, post_id: int, owner_id: Optional[int] = None) -> Optional[int]:
        params = {"post_id": post_id}
        if owner_id:
            params["owner_id"] = owner_id
        return await self._make_request("wall.delete", params=params)

# --- backend/app\services\vk_api\__init__.py ---

# --- backend/app/services/vk_api/__init__.py ---

import aiohttp
import json
import asyncio
from typing import Optional, Dict, Any, List

from app.core.config import settings

# Экспортируем исключения для удобного доступа
from .base import VKAPIError, VKAuthError, VKAccessDeniedError, VKFloodControlError, VKCaptchaError, ERROR_CODE_MAP

# Импортируем все разделы API
from .account import AccountAPI
from .friends import FriendsAPI
from .groups import GroupsAPI
from .likes import LikesAPI
from .messages import MessagesAPI
from .newsfeed import NewsfeedAPI
from .photos import PhotosAPI
from .stories import StoriesAPI
from .users import UsersAPI
from .wall import WallAPI


class VKAPI:
    """
    Основной класс-фасад для взаимодействия с VK API.
    Предоставляет доступ к логическим разделам API через свои атрибуты.
    Пример: `vk_api.friends.get(...)`
    
    ИЗМЕНЕНИЕ: Класс теперь управляет жизненным циклом одного aiohttp.ClientSession
    для повышения производительности за счет переиспользования соединений.
    """
    def __init__(self, access_token: str, proxy: Optional[str] = None):
        self.access_token = access_token
        self.proxy = proxy
        self.api_version = settings.VK_API_VERSION
        self.base_url = "https://api.vk.com/method/"
        self._session: aiohttp.ClientSession | None = None
        
        # Инициализация всех разделов
        self.account = AccountAPI(self._make_request)
        self.friends = FriendsAPI(self._make_request)
        self.groups = GroupsAPI(self._make_request)
        self.likes = LikesAPI(self._make_request)
        self.messages = MessagesAPI(self._make_request)
        self.newsfeed = NewsfeedAPI(self._make_request)
        self.photos = PhotosAPI(self._make_request, self) # Передаем self для доступа к сессии
        self.stories = StoriesAPI(self._make_request)
        self.users = UsersAPI(self._make_request)
        self.wall = WallAPI(self._make_request)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Ленивая инициализация сессии aiohttp."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=20)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Закрывает сессию. Важно вызывать при завершении работы с объектом."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if params is None: params = {}
        
        params['access_token'] = self.access_token
        params['v'] = self.api_version

        session = await self._get_session()
        try:
            for attempt in range(3): # Логика повторных попыток сохранена
                async with session.post(f"{self.base_url}{method}", data=params, proxy=self.proxy) as response:
                    # Проверяем, что ответ действительно JSON, чтобы избежать ошибок
                    if response.content_type != 'application/json':
                         raw_text = await response.text()
                         raise VKAPIError(f"VK API вернул не-JSON ответ. Статус: {response.status}. Ответ: {raw_text[:200]}", 0)

                    data = await response.json()
                    
                    if 'error' in data:
                        error_data = data['error']
                        error_code = error_data.get('error_code')
                        error_msg = error_data.get('error_msg', 'Unknown VK error')
                        
                        if error_code in [6, 9]: # Rate Limit или Flood Control
                            wait_time = 1.5 + attempt * 2
                            await asyncio.sleep(wait_time)
                            continue

                        ExceptionClass = ERROR_CODE_MAP.get(error_code, VKAPIError)
                        raise ExceptionClass(error_msg, error_code)

                    return data.get('response')
            
            # Если все попытки исчерпаны
            raise VKFloodControlError("Превышено количество попыток после ошибок Flood/Rate Control.", 9)

        except aiohttp.ClientError as e:
            # Более детальное сообщение об ошибке
            raise VKAPIError(f"Сетевая ошибка ({type(e).__name__}): {e}. Проверьте прокси и подключение к интернету.", 0)

    async def execute(self, calls: List[Dict[str, Any]]) -> Optional[List[Any]]:
        if not 25 >= len(calls) > 0:
            raise ValueError("Количество вызовов для метода execute должно быть от 1 до 25.")
        # Использование f-строк и json.dumps для большей безопасности и читаемости
        code_lines = [f'API.{call["method"]}({json.dumps(call.get("params", {}), ensure_ascii=False)})' for call in calls]
        code = f"return [{','.join(code_lines)}];"
        return await self._make_request("execute", params={"code": code})
    
    async def get_user_friends(self, user_id: int, fields: str = "sex,online,last_seen,is_closed,deactivated") -> Optional[Dict[str, Any]]:
        """
        Удобный метод-обертка для получения списка друзей пользователя.
        ВОЗВРАЩАЕТ ПОЛНЫЙ СЛОВАРЬ ОТВЕТА VK API.
        """
        return await self.friends.get(user_id=user_id, fields=fields)

    async def get_recommended_friends(self, count: int = 200) -> Optional[Dict[str, Any]]:
        """
        Удобный метод-обертка для получения рекомендованных друзей.
        """
        return await self.friends.getSuggestions(count=count)
    
    async def add_friend(self, user_id: int, text: Optional[str] = None) -> Optional[int]:
        """
        Удобный метод-обертка для отправки заявки в друзья.
        """
        return await self.friends.add(user_id=user_id, text=text)
    
    async def add_like(self, item_type: str, owner_id: int, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Удобный метод-обертка для простановки лайка.
        """
        return await self.likes.add(item_type=item_type, owner_id=owner_id, item_id=item_id)

    async def get_incoming_friend_requests(self, extended: int = 0, count: int = 1000) -> Optional[Dict[str, Any]]:
        """
        Удобный метод-обертка для получения входящих заявок в друзья.
        """
        return await self.friends.getRequests(extended=extended, count=count)
    
    async def get_wall(self, owner_id: int, count: int = 5) -> Optional[Dict[str, Any]]:
            """
            Удобный метод-обертка для получения постов со стены.
            """
            return await self.wall.get(owner_id=owner_id, count=count)
    
    async def get_conversations(self, count: int = 200, filter: str = 'all') -> Optional[Dict[str, Any]]:
        """
        Удобный метод-обертка для получения диалогов.
        """
        return await self.messages.getConversations(count=count, filter=filter)


async def is_token_valid(vk_token: str) -> Optional[int]:
    """Вспомогательная функция для проверки токена при логине."""
    vk_api = VKAPI(access_token=vk_token)
    try:
        user_info_list = await vk_api.users.get()
        if user_info_list and isinstance(user_info_list, list) and len(user_info_list) > 0:
            user_info = user_info_list[0]
            return user_info.get('id') if user_info else None
        return None
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---
    except VKAPIError:
        return None
    finally:
        # Важно закрыть сессию после использования
        await vk_api.close()

# --- backend/app\tasks\cron_jobs.py ---

# --- backend/app/tasks/cron_jobs.py ---
from app.tasks.logic.analytics_jobs import (
    _aggregate_daily_stats_async,
    _generate_all_heatmaps_async,
    _update_friend_request_statuses_async,
    _snapshot_all_users_metrics_async
)
from app.tasks.logic.maintenance_jobs import _check_expired_plans_async
from app.tasks.logic.automation_jobs import _run_daily_automations_async

async def aggregate_daily_stats_job(ctx):
    await _aggregate_daily_stats_async()

async def snapshot_all_users_metrics_job(ctx):
    await _snapshot_all_users_metrics_async()

async def check_expired_plans_job(ctx):
    await _check_expired_plans_async()

async def generate_all_heatmaps_job(ctx):
    await _generate_all_heatmaps_async()

async def update_friend_request_statuses_job(ctx):
    await _update_friend_request_statuses_async()

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

# --- backend/app/tasks/maintenance_jobs.py ---
from app.tasks.logic.maintenance_jobs import _clear_old_task_history_async

async def clear_old_task_history_job(ctx):
    """ARQ-задача для очистки старой истории задач."""
    await _clear_old_task_history_async()

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

# --- backend/app\tasks\standard_tasks.py ---

# backend/app/tasks/standard_tasks.py

import functools
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.models import User, TaskHistory, Automation
from app.db.session import AsyncSessionFactory
from app.services.event_emitter import RedisEventEmitter
from app.core.exceptions import UserActionException
from app.services.vk_api import VKAPIError, VKAuthError
from app.core.constants import TaskKey
from app.tasks.service_maps import TASK_CONFIG_MAP
from contextlib import asynccontextmanager

log = structlog.get_logger(__name__)


def arq_task_runner(func):
    @functools.wraps(func)
    async def wrapper(ctx, task_history_id: int, **kwargs):
        session_for_test = kwargs.pop("session_for_test", None)
        emitter_for_test = kwargs.pop("emitter_for_test", None)

        @asynccontextmanager
        async def get_session_context():
            if session_for_test:
                yield session_for_test
            else:
                async with AsyncSessionFactory() as session:
                    yield session
        
        async with get_session_context() as session:
            task_history = None
            emitter = None
            task_name = "Неизвестная задача"
            created_at = None
            user_id = None
            
            try:
                stmt = select(TaskHistory).where(TaskHistory.id == task_history_id).options(
                    joinedload(TaskHistory.user).selectinload(User.proxies)
                )
                task_history = (await session.execute(stmt)).scalar_one_or_none()

                if not task_history or not task_history.user:
                    log.error("task.runner.not_found_final", task_history_id=task_history_id)
                    return

                task_name = task_history.task_name
                created_at = task_history.created_at
                user_id = task_history.user.id

                emitter = emitter_for_test or RedisEventEmitter(ctx['redis_pool'])
                emitter.set_context(user_id, task_history_id)
                
                task_history.status = "STARTED"
                await session.commit()
                
                await emitter.send_task_status_update(status="STARTED", task_name=task_name, created_at=created_at)

                summary_result = await func(session, task_history.user, task_history.parameters or {}, emitter)

                task_history.status = "SUCCESS"
                task_history.result = summary_result if isinstance(summary_result, str) else "Задача успешно выполнена."

            except (UserActionException, VKAPIError, VKAuthError) as e:
                if task_history:
                    await session.rollback()
                    task_history.status = "FAILURE"
                    if isinstance(e, VKAuthError):
                        task_history.result = "Ошибка авторизации VK. Токен невалиден."
                        log.error("task_runner.auth_error_critical", user_id=user_id)
                        if emitter: await emitter.send_system_notification(session, f"Критическая ошибка: токен VK недействителен для задачи '{task_name}'. Автоматизации остановлены.", "error")
                        await session.execute(update(Automation).where(Automation.user_id == user_id).values(is_active=False))
                    else:
                        error_message = str(getattr(e, 'message', e))
                        task_history.result = f"Ошибка: {error_message}"
                        if emitter: await emitter.send_system_notification(session, f"Задача '{task_name}' завершилась с ошибкой: {error_message}", "error")

            except Exception as e:
                if task_history:
                    await session.rollback()
                    task_history.status = "FAILURE"
                    task_history.result = f"Внутренняя ошибка сервера: {type(e).__name__}"
                    log.exception("task_runner.unhandled_exception", id=task_history_id)
                    if emitter: await emitter.send_system_notification(session, f"Задача '{task_name}' завершилась из-за внутренней ошибки сервера.", "error")
            
            finally:
                if task_history:
                    final_status = task_history.status
                    final_result = task_history.result
                    
                    await session.commit()
                    
                    if emitter:
                        await emitter.send_task_status_update(
                            status=final_status,
                            result=final_result,
                            task_name=task_name,
                            created_at=created_at
                        )
    return wrapper


async def _run_service_method(session, user, params, emitter, task_key: TaskKey):
    """Вспомогательная функция: находит нужный сервис и метод по ключу и выполняет его."""
    ServiceClass, method_name, ParamsModel = TASK_CONFIG_MAP[task_key]
    validated_params = ParamsModel(**params)
    service_instance = ServiceClass(db=session, user=user, emitter=emitter)
    return await getattr(service_instance, method_name)(validated_params)


@arq_task_runner
async def like_feed_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.LIKE_FEED)

@arq_task_runner
async def add_recommended_friends_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.ADD_RECOMMENDED)

@arq_task_runner
async def accept_friend_requests_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.ACCEPT_FRIENDS)

@arq_task_runner
async def remove_friends_by_criteria_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.REMOVE_FRIENDS)

@arq_task_runner
async def view_stories_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.VIEW_STORIES)

@arq_task_runner
async def birthday_congratulation_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.BIRTHDAY_CONGRATULATION)

@arq_task_runner
async def mass_messaging_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.MASS_MESSAGING)

@arq_task_runner
async def eternal_online_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.ETERNAL_ONLINE)

@arq_task_runner
async def leave_groups_by_criteria_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.LEAVE_GROUPS)

@arq_task_runner
async def join_groups_by_criteria_task(session, user, params, emitter):
    return await _run_service_method(session, user, params, emitter, TaskKey.JOIN_GROUPS)

# --- backend/app\tasks\system_tasks.py ---

# backend/app/tasks/system_tasks.py

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload, Session
from contextlib import asynccontextmanager

from app.db.models import ScheduledPost, ScheduledPostStatus
from app.db.session import AsyncSessionFactory
from app.services.vk_api import VKAPI, VKAPIError
from app.core.security import decrypt_data
from app.services.scenario_service import ScenarioExecutionService
from app.services.event_emitter import RedisEventEmitter

log = structlog.get_logger(__name__)


@asynccontextmanager
async def get_task_db_session(provided_session: Session | None = None):
    """
    Контекстный менеджер для получения сессии БД.
    Если сессия передана извне (как в тестах), использует ее.
    Иначе, создает новую сессию (как в production).
    """
    if provided_session:
        yield provided_session
    else:
        async with AsyncSessionFactory() as session:
            yield session


async def publish_scheduled_post_task(ctx, post_id: int, db_session_for_test: Session | None = None):
    """
    ARQ-задача для публикации отложенного поста.
    Может принимать существующую сессию БД для целей тестирования.
    """
    async with get_task_db_session(db_session_for_test) as session:
        post = await session.get(ScheduledPost, post_id, options=[selectinload(ScheduledPost.user)])
        
        if not post or post.status != ScheduledPostStatus.scheduled:
            if not post:
                log.warn("publish_post.not_found", post_id=post_id)
            return

        user = post.user
        emitter = RedisEventEmitter(ctx['redis_pool'])
        emitter.set_context(user.id)

        if not user:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Пользователь не найден"
            if not db_session_for_test:
                await session.commit()
            return

        vk_token = decrypt_data(user.encrypted_vk_token)
        if not vk_token:
            post.status = ScheduledPostStatus.failed
            post.error_message = "Токен пользователя недействителен"
            await emitter.send_system_notification(session, "Не удалось опубликовать пост: токен VK недействителен.", "error")
            if not db_session_for_test:
                await session.commit()
            return

        vk_api = VKAPI(access_token=vk_token)
        try:
            attachments_str = ",".join(post.attachments or [])
            result = await vk_api.wall.post(
                owner_id=int(post.vk_profile_id),
                message=post.post_text or "",
                attachments=attachments_str
            )
            if result and result.get("post_id"):
                post.status = ScheduledPostStatus.published
                post.vk_post_id = str(result.get("post_id"))
                await emitter.send_system_notification(session, "Запланированный пост успешно опубликован.", "success")
            else:
                 raise VKAPIError(f"Не удалось опубликовать пост. Ответ VK: {result}", 0)

        except (VKAPIError, Exception) as e:
            error_message = str(e.message) if isinstance(e, VKAPIError) else str(e)
            post.status = ScheduledPostStatus.failed
            post.error_message = error_message
            log.error("post_scheduler.failed", post_id=post.id, user_id=user.id, error=error_message)
            await emitter.send_system_notification(session, f"Ошибка публикации поста: {error_message}", "error")
        finally:
            await vk_api.close()

        # Коммитим изменения только если мы не в режиме теста
        if db_session_for_test:
            await session.flush()
        # В рабочем режиме коммитим транзакцию
        else:
            await session.commit()


async def run_scenario_from_scheduler_task(ctx, scenario_id: int, user_id: int, db_session_for_test: Session | None = None):
    """
    ARQ-задача для запуска сценария по расписанию.
    Может принимать существующую сессию БД для целей тестирования.
    """
    log.info("scenario.runner.start", scenario_id=scenario_id, user_id=user_id)
    try:
        async with get_task_db_session(db_session_for_test) as session:
            executor = ScenarioExecutionService(session, scenario_id, user_id)
            await executor.run()
    except Exception as e:
        log.error("scenario.runner.critical_error", scenario_id=scenario_id, error=str(e), exc_info=True)
    finally:
        log.info("scenario.runner.finished", scenario_id=scenario_id)

# --- backend/app\tasks\task_maps.py ---

# backend/app/tasks/task_maps.py

"""
Централизованный модуль для хранения карт и определений, связанных с задачами.
Это помогает избежать циклических зависимостей и упрощает добавление новых задач.
"""
from typing import Union

# --- Сервисы, используемые для выполнения задач ---
from app.services.feed_service import FeedService
from app.services.incoming_request_service import IncomingRequestService
from app.services.outgoing_request_service import OutgoingRequestService
from app.services.friend_management_service import FriendManagementService
from app.services.story_service import StoryService
from app.services.automation_service import AutomationService
from app.services.message_service import MessageService
from app.services.group_management_service import GroupManagementService

# --- Схемы данных (параметры) для каждой задачи ---
from app.api.schemas.actions import (
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest,
    BirthdayCongratulationRequest, EternalOnlineRequest
)

# --- Ключи задач ---
from app.core.constants import TaskKey

# 1. Объединенный тип для всех возможных моделей с параметрами задач
AnyTaskRequest = Union[
    AcceptFriendsRequest, LikeFeedRequest, AddFriendsRequest, EmptyRequest,
    RemoveFriendsRequest, MassMessagingRequest, JoinGroupsRequest, LeaveGroupsRequest,
    BirthdayCongratulationRequest, EternalOnlineRequest
]

# 2. Карта, связывающая ключ задачи с именем функции-исполнителя в ARQ
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

# 3. Карта для функции предпросмотра, связывающая ключ задачи с сервисным методом
PREVIEW_SERVICE_MAP = {
    TaskKey.ADD_RECOMMENDED: (OutgoingRequestService, "get_add_recommended_targets", AddFriendsRequest),
    TaskKey.ACCEPT_FRIENDS: (IncomingRequestService, "get_accept_friends_targets", AcceptFriendsRequest),
    TaskKey.REMOVE_FRIENDS: (FriendManagementService, "get_remove_friends_targets", RemoveFriendsRequest),
    TaskKey.MASS_MESSAGING: (MessageService, "get_mass_messaging_targets", MassMessagingRequest),
    TaskKey.LEAVE_GROUPS: (GroupManagementService, "get_leave_groups_targets", LeaveGroupsRequest),
    TaskKey.JOIN_GROUPS: (GroupManagementService, "get_join_groups_targets", JoinGroupsRequest),
    TaskKey.BIRTHDAY_CONGRATULATION: (AutomationService, "get_birthday_congratulation_targets", BirthdayCongratulationRequest),
}

# --- backend/app\tasks\__init__.py ---



# --- backend/app\tasks\logic\analytics_jobs.py ---

# --- START OF FILE backend/app/tasks/logic/analytics_jobs.py ---

import datetime
import structlog
import pytz
from contextlib import asynccontextmanager
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionFactory
from app.db.models import (
    DailyStats, WeeklyStats, MonthlyStats, User, FriendRequestLog, FriendRequestStatus,
    ProfileMetric
)
from app.services.event_emitter import SystemLogEmitter
from app.services.vk_api import VKAPI, VKAuthError
from app.core.security import decrypt_data
from app.services.analytics_service import AnalyticsService
from app.services.profile_analytics_service import ProfileAnalyticsService

log = structlog.get_logger(__name__)

@asynccontextmanager
async def get_session(provided_session: AsyncSession | None = None):
    """
    Контекстный менеджер для получения сессии БД.
    Если сессия передана извне (как в тестах), использует ее.
    Иначе, создает новую сессию (как в production).
    """
    if provided_session:
        yield provided_session
    else:
        async with AsyncSessionFactory() as session:
            yield session

async def _aggregate_daily_stats_async():
    """Агрегирует вчерашнюю дневную статистику в недельную и месячную."""
    async with AsyncSessionFactory() as session:
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        
        stmt = select(
            DailyStats.user_id,
            func.sum(DailyStats.likes_count).label("likes"),
            func.sum(DailyStats.friends_added_count).label("friends"),
            func.sum(DailyStats.friend_requests_accepted_count).label("accepted")
        ).where(DailyStats.date == yesterday).group_by(DailyStats.user_id)
        
        daily_sums = (await session.execute(stmt)).all()
        if not daily_sums:
            return

        week_id, month_id = yesterday.strftime('%Y-%W'), yesterday.strftime('%Y-%m')

        for stat_type, identifier in [(WeeklyStats, week_id), (MonthlyStats, month_id)]:
            values_to_upsert = []
            for r in daily_sums:
                values_to_upsert.append({
                    "user_id": r.user_id,
                    f"{stat_type.__tablename__.replace('s', '')}_identifier": identifier,
                    "likes_count": r.likes,
                    "friends_added_count": r.friends,
                    "friend_requests_accepted_count": r.accepted
                })

            if not values_to_upsert:
                continue
            
            # В SQLAlchemy 2.0+ on_conflict_do_update строится немного иначе
            from sqlalchemy.dialects.postgresql import insert
            
            insert_stmt = insert(stat_type).values(values_to_upsert)
            
            # Определяем, как обновлять поля при конфликте
            update_dict = {
                'likes_count': getattr(stat_type, 'likes_count') + insert_stmt.excluded.likes_count,
                'friends_added_count': getattr(stat_type, 'friends_added_count') + insert_stmt.excluded.friends_added_count,
                'friend_requests_accepted_count': getattr(stat_type, 'friend_requests_accepted_count') + insert_stmt.excluded.friend_requests_accepted_count
            }
            
            # Собираем окончательный запрос
            final_stmt = insert_stmt.on_conflict_do_update(
                index_elements=['user_id', f"{stat_type.__tablename__.replace('s', '')}_identifier"],
                set_=update_dict
            )
            await session.execute(final_stmt)
        
        await session.commit()
        log.info("analytics.aggregated_daily_stats", count=len(daily_sums), date=yesterday.isoformat())

async def _snapshot_all_users_metrics_async(session_for_test: AsyncSession | None = None):
    """Создает снимок ключевых метрик профиля для всех активных пользователей."""
    async with get_session(session_for_test) as session:
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(User).where(
            (User.plan_expires_at == None) | (User.plan_expires_at > now)
        )
        result = await session.execute(stmt)
        active_users = result.scalars().all()

        if not active_users:
            log.info("snapshot_metrics_task.no_active_users")
            return

        log.info("snapshot_metrics_task.start", count=len(active_users))

        for user in active_users:
            try:
                async with session.begin_nested():
                    # Создаем сервис с той же сессией
                    service = ProfileAnalyticsService(db=session, user=user, emitter=SystemLogEmitter("snapshot_metrics"))
                    await service.snapshot_profile_metrics()
                # begin_nested() автоматически коммитит, если не было ошибок
            except VKAuthError:
                log.warn("snapshot_metrics_task.auth_error", user_id=user.id)
                # Роллбэк для этого пользователя произойдет автоматически при выходе из блока `begin_nested`
            except Exception as e:
                log.error("snapshot_metrics_task.user_error", user_id=user.id, error=str(e), exc_info=True)

        if not session_for_test:
            await session.commit()

        log.info("snapshot_metrics_task.finished")


async def _generate_all_heatmaps_async():
    """Генерирует тепловые карты активности для всех пользователей с доступом к фиче."""
    async with AsyncSessionFactory() as session:
        users = (await session.execute(select(User).where(User.plan.in_(['PLUS', 'PRO', 'AGENCY'])))).scalars().all()
        if not users: return
        
        log.info("analytics.heatmap_generation_started", count=len(users))
        for user in users:
            try:
                async with AsyncSessionFactory() as user_session:
                    async with user_session.begin():
                        emitter = SystemLogEmitter(task_name="heatmap_generator")
                        emitter.set_context(user_id=user.id)
                        service = AnalyticsService(db=user_session, user=user, emitter=emitter)
                        await service.generate_post_activity_heatmap()
            except Exception as e:
                log.error("analytics.heatmap_generation_user_error", user_id=user.id, error=str(e))

async def _update_friend_request_statuses_async():
    """Проверяет статусы отправленных заявок в друзья (приняты или нет)."""
    async with AsyncSessionFactory() as session:
        # Находим пользователей, у которых есть заявки в статусе 'pending'
        stmt = select(User).options(selectinload(User.friend_requests)).where(
            User.friend_requests.any(FriendRequestLog.status == FriendRequestStatus.pending)
        )
        users_with_pending_reqs = (await session.execute(stmt)).scalars().unique().all()
        
        if not users_with_pending_reqs:
            return

        log.info("analytics.conversion_tracker_started", count=len(users_with_pending_reqs))
        
        for user in users_with_pending_reqs:
            pending_reqs = [req for req in user.friend_requests if req.status == FriendRequestStatus.pending]
            if not pending_reqs:
                continue

            vk_api = None
            try:
                vk_token = decrypt_data(user.encrypted_vk_token)
                if not vk_token:
                    log.warn("analytics.conversion_tracker_no_token", user_id=user.id)
                    continue

                vk_api = VKAPI(access_token=vk_token)
                
                # Получаем актуальный список ID друзей
                friends_response = await vk_api.get_user_friends(user_id=user.vk_id, fields="")
                if not friends_response or 'items' not in friends_response:
                    continue
                
                friend_ids = set(friends_response['items'])
                
                accepted_req_ids = [req.id for req in pending_reqs if req.target_vk_id in friend_ids]
                
                if accepted_req_ids:
                    update_stmt = update(FriendRequestLog).where(FriendRequestLog.id.in_(accepted_req_ids)).values(
                        status=FriendRequestStatus.accepted, 
                        resolved_at=datetime.datetime.now(pytz.utc)
                    )
                    await session.execute(update_stmt)
                    await session.commit()
                    log.info("analytics.conversion_tracker_updated", user_id=user.id, count=len(accepted_req_ids))

            except VKAuthError:
                log.warn("analytics.conversion_tracker_auth_error", user_id=user.id)
            except Exception as e:
                log.error("analytics.conversion_tracker_user_error", user_id=user.id, error=str(e))
            finally:
                if vk_api:
                    await vk_api.close()



# --- backend/app\tasks\logic\automation_jobs.py ---

# --- backend/app/tasks/logic/automation_jobs.py ---
import datetime
import structlog
import pytz
import random
from redis.asyncio import Redis
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

# --- ИСПРАВЛЕНИЕ: Добавляем недостающий импорт ---
from app.core.config import settings
# -----------------------------------------------

from app.db.session import AsyncSessionFactory
from app.db.models import Automation, TaskHistory, User
from app.core.config_loader import AUTOMATIONS_CONFIG
from app.core.constants import CronSettings

log = structlog.get_logger(__name__)

# Эта карта нужна для постановки ARQ задач из этого модуля
TASK_FUNC_MAP_ARQ = {
    "accept_friends": "accept_friend_requests_task", "like_feed": "like_feed_task",
    "add_recommended": "add_recommended_friends_task", "view_stories": "view_stories_task",
    "remove_friends": "remove_friends_by_criteria_task", "mass_messaging": "mass_messaging_task",
    "join_groups": "join_groups_by_criteria_task", "leave_groups": "leave_groups_by_criteria_task",
    "birthday_congratulation": "birthday_congratulation_task", "eternal_online": "eternal_online_task",
}

async def _create_and_run_arq_task(session, arq_pool, user_id, task_name_key, settings_dict):
    """Вспомогательная функция для создания TaskHistory и постановки задачи в ARQ."""
    task_func_name = TASK_FUNC_MAP_ARQ.get(task_name_key)
    if not task_func_name:
        log.warn("cron.arq_task_not_found", task_name=task_name_key)
        return

    task_config = next((item for item in AUTOMATIONS_CONFIG if item.id == task_name_key), None)
    display_name = task_config.name if task_config else "Автоматическая задача"

    task_history = TaskHistory(user_id=user_id, task_name=display_name, status="PENDING", parameters=settings_dict)
    session.add(task_history)
    await session.flush()

    job = await arq_pool.enqueue_job(task_func_name, task_history_id=task_history.id, **(settings_dict or {}))
    task_history.arq_job_id = job.job_id
    await session.commit()

async def _run_daily_automations_async(automation_group: str):
    """
    Основная логика для запуска автоматизаций. Находит все активные автоматизации
    в указанной группе, проверяет их расписание и ставит в очередь ARQ.
    """
    from app.worker import redis_settings
    from arq.connections import create_pool

    redis_lock_client = await Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/2", decode_responses=True)
    lock_key = f"lock:task:run_automations:{automation_group}"

    lock_acquired = await redis_lock_client.set(lock_key, "1", ex=CronSettings.AUTOMATION_JOB_LOCK_EXPIRATION_SECONDS, nx=True)
    if not lock_acquired:
        log.warn("run_daily_automations.already_running", group=automation_group)
        await redis_lock_client.close()
        return

    arq_pool = await create_pool(redis_settings)
    try:
        async with AsyncSessionFactory() as session:
            now_utc = datetime.datetime.now(pytz.utc)
            moscow_tz = pytz.timezone("Europe/Moscow")
            now_moscow = now_utc.astimezone(moscow_tz)

            automation_ids = [item.id for item in AUTOMATIONS_CONFIG if item.group == automation_group]
            if not automation_ids:
                return

            stmt = select(Automation).join(User).where(
                Automation.is_active == True,
                Automation.automation_type.in_(automation_ids),
                or_(User.plan_expires_at.is_(None), User.plan_expires_at > now_utc)
            ).options(selectinload(Automation.user))
            
            automations = (await session.execute(stmt)).scalars().unique().all()
            if not automations:
                return
                
            log.info("run_daily_automations.start", count=len(automations), group=automation_group)

            for automation in automations:
                if automation.automation_type == 'eternal_online':
                    automation_settings = automation.settings or {} # Используем другую переменную, чтобы не конфликтовать с глобальным `settings`
                    if automation_settings.get('mode', 'schedule') == 'schedule':
                        day_key = str(now_moscow.isoweekday())
                        day_schedule = automation_settings.get('schedule_weekly', {}).get(day_key)

                        if not day_schedule or not day_schedule.get('is_active'):
                            continue

                        try:
                            start = datetime.datetime.strptime(day_schedule.get('start_time', '00:00'), '%H:%M').time()
                            end = datetime.datetime.strptime(day_schedule.get('end_time', '23:59'), '%H:%M').time()
                            
                            if not (start <= now_moscow.time() <= end):
                                continue
                            if automation_settings.get('humanize', True) and random.random() < CronSettings.HUMANIZE_ONLINE_SKIP_CHANCE:
                                log.info("eternal_online.humanizer_skip", user_id=automation.user_id)
                                continue
                        except (ValueError, TypeError):
                            log.warn("eternal_online.invalid_time_format", user_id=automation.user_id, schedule=day_schedule)
                            continue
                
                automation.last_run_at = now_utc
                await _create_and_run_arq_task(session, arq_pool, automation.user_id, automation.automation_type, automation.settings)

    finally:
        await redis_lock_client.delete(lock_key)
        await redis_lock_client.close()
        await arq_pool.close()

# --- backend/app\tasks\logic\maintenance_jobs.py ---

# app/tasks/logic/maintenance_jobs.py
import datetime
import structlog
from sqlalchemy import delete, select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from app.db.session import AsyncSessionFactory
from app.db.models import TaskHistory, User, Automation, Notification
from app.core.plans import get_limits_for_plan
from app.core.constants import CronSettings, PlanName

log = structlog.get_logger(__name__)

@asynccontextmanager
async def get_session(provided_session: AsyncSession | None = None):
    """Контекстный менеджер для получения сессии БД."""
    if provided_session:
        yield provided_session
    else:
        async with AsyncSessionFactory() as session:
            yield session

async def _clear_old_task_history_async():
    """Удаляет старые записи из TaskHistory согласно настройкам хранения."""
    async with AsyncSessionFactory() as session:
        # (код этой функции остается без изменений)
        pro_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=CronSettings.TASK_HISTORY_RETENTION_DAYS_PRO)
        stmt_pro = delete(TaskHistory).where(
            TaskHistory.user_id.in_(select(User.id).filter(User.plan.in_(['PRO', 'Plus', 'Agency']))),
            TaskHistory.created_at < pro_cutoff
        )
        pro_result = await session.execute(stmt_pro)
        base_cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=CronSettings.TASK_HISTORY_RETENTION_DAYS_BASE)
        stmt_base = delete(TaskHistory).where(
            TaskHistory.user_id.in_(
                select(User.id).filter(User.plan.in_([PlanName.BASE.name, PlanName.EXPIRED.name]))
            ),
            TaskHistory.created_at < base_cutoff
        )
        base_result = await session.execute(stmt_base)
        await session.commit()
        total_deleted = pro_result.rowcount + base_result.rowcount
        if total_deleted > 0:
            log.info("maintenance.task_history_cleaned", count=total_deleted)

async def _check_expired_plans_async(session_for_test: AsyncSession | None = None):
    """Проверяет и деактивирует истекшие тарифные планы пользователей."""
    # --- ИСПРАВЛЕНИЕ: Используем контекстный менеджер ---
    async with get_session(session_for_test) as session:
        now = datetime.datetime.now(datetime.UTC)
        stmt = select(User).where(User.plan != 'Expired', User.plan_expires_at != None, User.plan_expires_at < now)
        expired_users = (await session.execute(stmt)).scalars().all()

        if not expired_users:
            return

        log.info("maintenance.expired_plans_found", count=len(expired_users))
        expired_plan_limits = get_limits_for_plan("Expired")
        user_ids_to_deactivate = [user.id for user in expired_users]

        notifications = [Notification(user_id=user.id, message=f"Срок действия тарифа '{user.plan}' истек.", level="error") for user in expired_users]
        session.add_all(notifications)

        await session.execute(update(Automation).where(Automation.user_id.in_(user_ids_to_deactivate)).values(is_active=False))
        
        await session.execute(update(User).where(User.id.in_(user_ids_to_deactivate)).values(
            plan="Expired",
            daily_likes_limit=expired_plan_limits["daily_likes_limit"],
            daily_add_friends_limit=expired_plan_limits["daily_add_friends_limit"],
            daily_message_limit=expired_plan_limits["daily_message_limit"],
            daily_posts_limit=expired_plan_limits["daily_posts_limit"],
            daily_join_groups_limit=expired_plan_limits["daily_join_groups_limit"],
            daily_leave_groups_limit=expired_plan_limits["daily_leave_groups_limit"]
        ))
        
        # Коммит делается, только если мы не в тесте
        if not session_for_test:
            await session.commit()
        else:
            await session.flush()
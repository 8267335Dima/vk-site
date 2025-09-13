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

from app.celery_app import celery_app

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

configure_logging()
log = structlog.get_logger(__name__)

# ИЗМЕНЕНИЕ: Улучшенная идентификация клиента для Rate Limiter
async def get_request_identifier(request: Request) -> str:
    """
    Получает реальный IP-адрес клиента, даже если приложение за прокси.
    Важно: Убедитесь, что ваш прокси (Nginx, Traefik) устанавливает заголовок 'X-Forwarded-For'.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Самый левый IP в списке - это исходный IP клиента
        return forwarded_for.split(',')[0].strip()
    # Fallback на прямое подключение
    return request.client.host if request.client else "unknown"

# Зависимости Rate Limiter
rate_limit_dependency = Depends(RateLimiter(times=20, minutes=1, identifier=get_request_identifier))

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
    except RedisError as e:
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

# --- Объявление тегов для OpenAPI ---
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
api_router_v1.include_router(proxies_router, prefix="/proxies", tags=[Tags.PROXIES], dependencies=[rate_limit_dependency])
api_router_v1.include_router(tasks_router, prefix="/tasks", tags=[Tags.TASKS])
api_router_v1.include_router(stats_router, prefix="/stats", tags=[Tags.STATS])
api_router_v1.include_router(automations_router, prefix="/automations", tags=[Tags.AUTOMATIONS])
api_router_v1.include_router(billing_router, prefix="/billing", tags=[Tags.BILLING], dependencies=[rate_limit_dependency])
api_router_v1.include_router(analytics_router, prefix="/analytics", tags=[Tags.ANALYTICS])
api_router_v1.include_router(scenarios_router, prefix="/scenarios", tags=[Tags.SCENARIOS], dependencies=[rate_limit_dependency])
api_router_v1.include_router(notifications_router, prefix="/notifications", tags=[Tags.NOTIFICATIONS])
api_router_v1.include_router(posts_router, prefix="/posts", tags=[Tags.POSTS])
api_router_v1.include_router(teams_router, prefix="/teams", tags=[Tags.TEAMS])
api_router_v1.include_router(websockets_router, prefix="", tags=[Tags.WEBSOCKETS])

app.include_router(api_router_v1, prefix="/api/v1")

@app.get("/api/health", status_code=status.HTTP_200_OK, tags=[Tags.SYSTEM])
async def health_check():
    return {"status": "ok"}
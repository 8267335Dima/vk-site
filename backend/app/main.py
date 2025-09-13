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
    tasks_router, posts_router, teams_router
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
api_router_v1.include_router(posts_router, prefix="/posts", tags=["Планировщик постов"])
api_router_v1.include_router(teams_router, prefix="/teams", tags=["Командный функционал"])
api_router_v1.include_router(websockets_router, prefix="", tags=["WebSockets"])

app.include_router(api_router_v1, prefix="/api/v1")

@app.get("/api/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check():
    return {"status": "ok"}
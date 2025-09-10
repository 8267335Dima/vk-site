# backend/app/main.py
import asyncio
import structlog
from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from contextlib import asynccontextmanager
from fastapi_limiter import FastAPILimiter

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.tracing import setup_tracing
from app.db.session import engine
from app.admin import init_admin
from app.api.endpoints import (
    auth_router, users_router, websockets_router,
    stats_router, automations_router, logs_router, billing_router,
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
        # Этот клиент для FastAPI-Limiter, ему нужно decode_responses=True
        redis_connection = Redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
            encoding="utf-8", decode_responses=True
        )
        await FastAPILimiter.init(redis_connection)
        
        # --- ИСПРАВЛЕНИЕ: Этот клиент для FastAPI-Cache, ему НЕ нужно decode_responses=True ---
        redis_cache_connection = Redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/3",
            encoding="utf-8" 
        )
        FastAPICache.init(RedisBackend(redis_cache_connection), prefix="fastapi-cache")
        
        # Этот клиент для Pub/Sub, ему НЕ нужно decode_responses
        redis_pubsub_connection = Redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1"
        )
        redis_task = asyncio.create_task(redis_listener(redis_pubsub_connection))
        
        log.info("lifespan.startup", message="Dependencies initialized.")
    except Exception as e:
        log.error("lifespan.startup.error", error=str(e), message="Could not connect to Redis.")
    
    yield
    
    if redis_task:
        redis_task.cancel()
        try:
            await redis_task
        except asyncio.CancelledError:
            log.info("lifespan.shutdown", message="Redis listener task cancelled.")

    await FastAPICache.clear()
    log.info("lifespan.shutdown", message="Resources cleaned up.")

app = FastAPI(
    title="Zenith Social API",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

setup_tracing(app)

@app.middleware("http")
async def admin_security_middleware(request: Request, call_next):
    if request.url.path.startswith("/admin"):
        if settings.ADMIN_IP_WHITELIST:
            whitelist = [ip.strip() for ip in settings.ADMIN_IP_WHITELIST.split(',')]
            if request.client.host not in whitelist:
                log.warn("admin.access_denied_ip", client_ip=request.client.host)
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Доступ с данного IP-адреса запрещен."},
                )
    response = await call_next(request)
    return response

init_admin(app, engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-name.onrender.com"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

api_router_v1 = APIRouter()
api_router_v1.include_router(auth_router, prefix="/auth", tags=["Аутентификация"])
api_router_v1.include_router(users_router, prefix="/users", tags=["Пользователи"])
api_router_v1.include_router(proxies_router, prefix="/proxies", tags=["Прокси"])
api_router_v1.include_router(tasks_router, prefix="/tasks", tags=["Задачи"])
api_router_v1.include_router(stats_router, prefix="/stats", tags=["Статистика"])
api_router_v1.include_router(automations_router, prefix="/automations", tags=["Автоматизации"])
api_router_v1.include_router(billing_router, prefix="/billing", tags=["Тарифы и оплата"])
api_router_v1.include_router(analytics_router, prefix="/analytics", tags=["Аналитика"])
api_router_v1.include_router(scenarios_router, prefix="/scenarios", tags=["Сценарии"])
api_router_v1.include_router(logs_router, prefix="/logs", tags=["История Действий"])
api_router_v1.include_router(notifications_router, prefix="/notifications", tags=["Уведомления"])
api_router_v1.include_router(websockets_router, prefix="", tags=["WebSockets"])

app.include_router(api_router_v1, prefix="/api/v1")

@app.get("/api/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check():
    return {"status": "ok"}
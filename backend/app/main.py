# backend/app/main.py

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine
from app.admin import init_admin
from app.services.websocket_manager import redis_listener
from app.api.endpoints import (
    auth_router, users_router, proxies_router, tasks_router,
    stats_router, automations_router, billing_router, analytics_router,
    scenarios_router, notifications_router, posts_router, teams_router,
    websockets_router, support_router
)

# Вызываем настройку логирования в самом начале
configure_logging()

# Создаем фоновую задачу для прослушивания Redis Pub/Sub для WebSockets
async def run_redis_listener(redis_client):
    await redis_listener(redis_client)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код, который выполнится при старте приложения
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
    await redis_client.close()


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
app.include_router(tasks_router, prefix=f"{api_prefix}/tasks", tags=["Tasks"])
app.include_router(stats_router, prefix=f"{api_prefix}/stats", tags=["Statistics"])
app.include_router(automations_router, prefix=f"{api_prefix}/automations", tags=["Automations"])
app.include_router(billing_router, prefix=f"{api_prefix}/billing", tags=["Billing"])
app.include_router(analytics_router, prefix=f"{api_prefix}/analytics", tags=["Analytics"])
app.include_router(support_router, prefix=f"{api_prefix}/support", tags=["Support"])
app.include_router(scenarios_router, prefix=f"{api_prefix}/scenarios", tags=["Scenarios"])
app.include_router(notifications_router, prefix=f"{api_prefix}/notifications", tags=["Notifications"])
app.include_router(posts_router, prefix=f"{api_prefix}/posts", tags=["Posts"])
app.include_router(teams_router, prefix=f"{api_prefix}/teams", tags=["Teams"])
app.include_router(websockets_router, tags=["WebSockets"])
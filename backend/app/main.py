import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis as AsyncRedis
from arq.connections import create_pool
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from datetime import datetime, UTC

from app.arq_config import redis_settings
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine as main_engine, get_db as get_db_session
from app.db.models import User
from app.admin import init_admin
from app.services.websocket_manager import redis_listener
from app.api.dependencies import get_current_active_profile, get_token_payload
from app.api.endpoints import (
    auth_router, users_router, proxies_router, tasks_router,
    stats_router, automations_router, billing_router, analytics_router,
    scenarios_router, notifications_router, posts_router, teams_router,
    websockets_router, support_router, task_history_router
)
from fastapi_limiter import FastAPILimiter

configure_logging()

async def run_redis_listener(redis_client):
    await redis_listener(redis_client)

def create_app(db_engine: AsyncEngine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        arq_pool = await create_pool(redis_settings)
        app.state.arq_pool = arq_pool

        limiter_redis = AsyncRedis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
            decode_responses=True
        )
        await FastAPILimiter.init(limiter_redis)

        redis_client = AsyncRedis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1",
            decode_responses=True
        )
        app.state.redis_client = redis_client
        app.state.activity_redis = AsyncRedis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/3")

        listener_task = asyncio.create_task(run_redis_listener(redis_client))

        yield

        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
        
        await app.state.activity_redis.aclose()
        await redis_client.aclose()
        await limiter_redis.aclose()
        await arq_pool.aclose()

    app = FastAPI(
        title="VK SMM Combine API",
        description="API для сервиса автоматизации SMM-задач ВКонтакте.",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY
    )

    origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def user_status_middleware(request: Request, call_next):
        is_api_route = request.url.path.startswith("/api/v1/")
        is_auth_route = request.url.path.startswith("/api/v1/auth")
        is_excluded_route = "webhook" in request.url.path or "/admin" in request.url.path or "/ws" in request.url.path

        if not is_api_route or is_auth_route or is_excluded_route:
            return await call_next(request)

        token = request.headers.get("authorization")
        if not token or "bearer" not in token.lower():
            return await call_next(request)
        
        db: AsyncSession = await anext(get_db_session())
        try:
            payload = await get_token_payload(token.split(" ")[1])
            user = await get_current_active_profile(payload=payload, db=db)
            
            if user.is_deleted:
                return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Аккаунт был удален."})
            if user.is_frozen:
                return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Ваш аккаунт временно заморожен администратором."})

            activity_redis = request.app.state.activity_redis
            last_update = await activity_redis.get(f"last_active:{user.id}")
            now_ts = datetime.now(UTC).timestamp()
            if not last_update or (now_ts - float(last_update)) > 60:
                await db.execute(update(User).where(User.id == user.id).values(last_active_at=datetime.now(UTC)))
                await db.commit()
                await activity_redis.set(f"last_active:{user.id}", now_ts, ex=65)
        except HTTPException:
             pass
        except Exception:
            pass 
        finally:
            await db.close()
            
        return await call_next(request)

    engine_to_use = db_engine or main_engine
    init_admin(app, engine_to_use)

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

    return app

app = create_app()
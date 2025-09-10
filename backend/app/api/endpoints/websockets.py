# backend/app/api/endpoints/websockets.py
from fastapi import APIRouter, WebSocket, status, Depends
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_user_from_token
from app.db.session import get_db, AsyncSessionFactory
from app.services.websocket_manager import manager
import structlog

from app.db.models import User

log = structlog.get_logger(__name__)
router = APIRouter()

async def get_user_from_ws_protocol(websocket: WebSocket, db: AsyncSession) -> "User":
    """
    Извлекает токен из subprotocol и аутентифицирует пользователя.
    """
    token = None
    # Ожидаемый формат: ['bearer', 'your_jwt_token']
    if websocket.scope.get("subprotocols"):
        protocols = websocket.scope["subprotocols"]
        if len(protocols) == 2 and protocols[0] == "bearer":
            token = protocols[1]

    if not token:
        log.warn("websocket.auth.token_missing")
        return None

    try:
        user = await get_user_from_token(token, db)
        return user
    except Exception:
        log.warn("websocket.auth.token_invalid", token=token)
        return None

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Эндпоинт для WebSocket-соединения.
    Аутентификация по токену в subprotocol.
    """
    async with AsyncSessionFactory() as session:
        user = await get_user_from_ws_protocol(websocket, session)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await manager.connect(websocket, user.id)
    log.info("websocket.connected", user_id=user.id)
    try:
        while True:
            # Оставляем открытым для получения сообщений от клиента, если понадобится
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        log.info("websocket.disconnected", user_id=user.id)
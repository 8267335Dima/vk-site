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
            # Просто поддерживаем соединение. Можно использовать receive_bytes,
            # если планируется прием данных от клиента.
            await websocket.receive_text() # Или receive_bytes()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        log.info("websocket.disconnected", user_id=user.id)
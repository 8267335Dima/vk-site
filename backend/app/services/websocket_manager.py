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
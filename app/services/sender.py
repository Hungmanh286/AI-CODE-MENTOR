from typing import Any

from fastapi import WebSocket
from pydantic import BaseModel
from starlette.websockets import WebSocketState


async def safe_send(websocket: WebSocket, message: Any, send_type: str = "json"):
    if websocket.client_state == WebSocketState.CONNECTED:
        if send_type == "json":
            send_message = (
                message.model_dump() if isinstance(message, BaseModel) else message
            )
            await websocket.send_json(send_message)
        else:
            await websocket.send_text(message)

import json
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class WSManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(session_id, []).append(ws)

    async def disconnect(self, session_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, session_id: str, event: dict[str, Any]) -> None:
        msg = json.dumps(event)
        dead: list[WebSocket] = []
        for ws in self._connections.get(session_id, []):
            try:
                await ws.send_text(msg)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)
        for ws in dead:
            await self.disconnect(session_id, ws)

    def active_sessions(self) -> list[str]:
        return [sid for sid, conns in self._connections.items() if conns]


ws_manager = WSManager()

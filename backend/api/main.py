import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

load_dotenv()

# noqa: E402 — must run after load_dotenv(); these modules read env vars at import time
from .routers import device_router, agent_router, kb_router, demonstrations_router  # noqa: E402
from .ws.manager import ws_manager  # noqa: E402
from ..device.registry import DeviceRegistry  # noqa: E402
from ..security.auth import ApiKeyAuthMiddleware, verify_ws_token  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    registry = DeviceRegistry()
    try:
        connected = await registry.discover_and_connect()
    except Exception as e:
        print(f"[startup] WARNING: device discovery failed: {e} — continue with zero devices")
        connected = []
    print(f"[startup] Connected to {len(connected)} device(s): {connected}")
    app.state.devices = registry

    from ..persistence import mark_stale_sessions_interrupted
    try:
        interrupted_count = await mark_stale_sessions_interrupted()
        print(f"[startup] Marked {interrupted_count} stale (mid-flight) session(s) as interrupted")
    except Exception as e:
        print(f"[startup] WARNING: failed to mark stale sessions interrupted: {e}")

    if not os.environ.get("API_KEY"):
        print(
            "[startup] SECURITY WARNING: API_KEY is not set — every endpoint is "
            "reachable by anyone who can reach this port, including the one that "
            "resolves credential-vault secrets. Set API_KEY in .env before "
            "exposing this beyond localhost."
        )

    yield

    # shutdown
    print("[shutdown] Mobile Agent API stopping")


app = FastAPI(
    title="Mobile Agent API",
    version="1.0.0",
    description="Autonomous Android agent — REST + WebSocket",
    lifespan=lifespan,
)

# Middleware runs in reverse-registration order (last added = outermost / runs
# first), so CORS must be added AFTER auth to actually wrap it and handle
# preflight before the auth check sees the request.
app.add_middleware(ApiKeyAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:80",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(device_router, prefix="/api/v1")
app.include_router(agent_router,  prefix="/api/v1")
app.include_router(kb_router,     prefix="/api/v1")
app.include_router(demonstrations_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    token = websocket.query_params.get("token")
    if not verify_ws_token(token):
        # Reject before accept() — never establish the connection for a bad/missing
        # token. 1008 = policy violation, the closest standard WS close code for this.
        await websocket.close(code=1008)
        return
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            # find session and apply control message
            from .routers.agent import _sessions
            state = _sessions.get(session_id)
            if state:
                if msg_type == "stop":
                    state.status = "done"
                elif msg_type == "pause":
                    state.status = "paused"
                elif msg_type == "resume":
                    state.status = "running"

    except WebSocketDisconnect:
        await ws_manager.disconnect(session_id, websocket)
    except Exception:
        await ws_manager.disconnect(session_id, websocket)

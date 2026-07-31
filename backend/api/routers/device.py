import asyncio
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from ...device import wireless
from ..schemas import (
    DeviceStatus, ScreenshotResponse, TapRequest,
    KeyEventRequest, OkResponse,
    PairDeviceRequest, ConnectDeviceRequest,
)

router = APIRouter(prefix="/device", tags=["device"])


def _ctrl(request: Request, serial: Optional[str] = None):
    registry = request.app.state.devices
    if serial:
        ctrl = registry.get(serial)
    else:
        statuses = registry.list_status()
        ctrl = registry.get(statuses[0]["serial"]) if statuses else None
    if ctrl is None or not ctrl.is_connected():
        raise HTTPException(status_code=503, detail="No Android device connected")
    return ctrl


@router.get("/status", response_model=DeviceStatus)
async def device_status(request: Request, serial: Optional[str] = None):
    registry = request.app.state.devices
    statuses = registry.list_status()
    if not statuses:
        return DeviceStatus(connected=False, message="Device controller not initialised")
    target = serial or statuses[0]["serial"]
    ctrl = registry.get(target)
    if ctrl is None or not ctrl.is_connected():
        return DeviceStatus(connected=False, message="Device not reachable")
    return DeviceStatus(
        connected=True,
        serial=ctrl.serial,
        resolution=list(ctrl.resolution),
        message="Connected",
    )


@router.get("/screenshot", response_model=ScreenshotResponse)
async def get_screenshot(request: Request, serial: Optional[str] = None):
    import base64
    ctrl = _ctrl(request, serial)
    raw = await ctrl.screenshot()
    return ScreenshotResponse(screenshot_b64=base64.b64encode(raw).decode())


@router.post("/tap", response_model=OkResponse)
async def tap(body: TapRequest, request: Request, serial: Optional[str] = None):
    ctrl = _ctrl(request, serial)
    await ctrl.tap(body.x, body.y)
    return OkResponse(ok=True)


@router.post("/keyevent", response_model=OkResponse)
async def key_event(body: KeyEventRequest, request: Request, serial: Optional[str] = None):
    ctrl = _ctrl(request, serial)
    await ctrl.key_event(body.code)
    return OkResponse(ok=True)


@router.get("/list")
async def list_devices(request: Request):
    return request.app.state.devices.list_status()


@router.post("/pair")
async def pair_device(body: PairDeviceRequest, request: Request):
    ok, output = await wireless.pair_device(body.ip, body.port, body.code)
    if not ok:
        raise HTTPException(status_code=502, detail=output)
    await request.app.state.devices.discover_and_connect()
    message = (
        output
        + " — now call /device/connect with the OTHER ip:port shown on the phone's "
        "Wireless debugging screen (the connect port differs from the pairing port)."
    )
    return {"paired": True, "message": message}


@router.post("/connect")
async def connect_device(body: ConnectDeviceRequest, request: Request):
    ok, output = await wireless.connect_device(body.ip, body.port)
    if not ok:
        raise HTTPException(status_code=502, detail=output)
    await request.app.state.devices.discover_and_connect()
    return request.app.state.devices.list_status()


async def _check_chromadb() -> dict:
    try:
        import chromadb
        from chromadb.config import Settings

        from ...knowledge_base.store import LOCAL_KB_PATH

        host = os.getenv("CHROMA_HOST")
        if host:
            client = chromadb.HttpClient(host=host, port=int(os.getenv("CHROMA_PORT", "8001")))
            await asyncio.to_thread(client.heartbeat)
            return {"reachable": True}
        client = chromadb.PersistentClient(
            path=str(LOCAL_KB_PATH), settings=Settings(anonymized_telemetry=False)
        )
        await asyncio.to_thread(client.heartbeat)
        return {"reachable": True, "mode": "local"}
    except Exception:
        return {"reachable": False}


async def _check_neo4j() -> dict:
    try:
        from ...graph.neo4j_client import NavigationGraph

        graph = NavigationGraph()
        try:
            await asyncio.to_thread(graph._driver.verify_connectivity)
            return {"reachable": True}
        finally:
            graph.close()
    except Exception:
        return {"reachable": False}


async def _check_langfuse() -> dict:
    from ...observability import langfuse_client

    return {"enabled": langfuse_client._enabled, "configured": langfuse_client._enabled}


async def _check_ollama() -> dict:
    try:
        url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/tags"
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            return {"reachable": resp.status_code == 200}
    except Exception:
        return {"reachable": False}


@router.get("/health/detailed")
async def health_detailed(request: Request):
    registry = request.app.state.devices
    statuses = registry.list_status()

    chromadb_status, neo4j_status, langfuse_status, ollama_status = await asyncio.gather(
        _check_chromadb(), _check_neo4j(), _check_langfuse(), _check_ollama()
    )

    return {
        "devices": {"count": len(statuses), "serials": [s["serial"] for s in statuses]},
        "chromadb": chromadb_status,
        "neo4j": neo4j_status,
        "langfuse": langfuse_status,
        "ollama": ollama_status,
    }

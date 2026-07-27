from typing import Optional

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
    return {"paired": True, "message": output + " — now call /device/connect with the OTHER ip:port shown on the phone's Wireless debugging screen (the connect port differs from the pairing port)."}


@router.post("/connect")
async def connect_device(body: ConnectDeviceRequest, request: Request):
    ok, output = await wireless.connect_device(body.ip, body.port)
    if not ok:
        raise HTTPException(status_code=502, detail=output)
    await request.app.state.devices.discover_and_connect()
    return request.app.state.devices.list_status()

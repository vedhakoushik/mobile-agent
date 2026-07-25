from fastapi import APIRouter, HTTPException, Request

from ..schemas import (
    DeviceStatus, ScreenshotResponse, TapRequest,
    KeyEventRequest, OkResponse,
)

router = APIRouter(prefix="/device", tags=["device"])


def _ctrl(request: Request):
    ctrl = request.app.state.device
    if ctrl is None or not ctrl.is_connected():
        raise HTTPException(status_code=503, detail="No Android device connected")
    return ctrl


@router.get("/status", response_model=DeviceStatus)
async def device_status(request: Request):
    ctrl = request.app.state.device
    if ctrl is None:
        return DeviceStatus(connected=False, message="Device controller not initialised")
    connected = ctrl.is_connected()
    w, h = ctrl.resolution if connected else (None, None)
    return DeviceStatus(
        connected=connected,
        serial=ctrl.serial,
        resolution=[w, h] if connected else None,
        message="Connected" if connected else "Device not reachable",
    )


@router.get("/screenshot", response_model=ScreenshotResponse)
async def get_screenshot(request: Request):
    import base64
    ctrl = _ctrl(request)
    raw = await ctrl.screenshot()
    return ScreenshotResponse(screenshot_b64=base64.b64encode(raw).decode())


@router.post("/tap", response_model=OkResponse)
async def tap(body: TapRequest, request: Request):
    ctrl = _ctrl(request)
    await ctrl.tap(body.x, body.y)
    return OkResponse(ok=True)


@router.post("/keyevent", response_model=OkResponse)
async def key_event(body: KeyEventRequest, request: Request):
    ctrl = _ctrl(request)
    await ctrl.key_event(body.code)
    return OkResponse(ok=True)

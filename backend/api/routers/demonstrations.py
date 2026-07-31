import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..schemas import (
    StartRecordingRequest, RecordStepRequest, StopRecordingRequest,
    ReplayRequest, StartRecordingResponse, RecordStepResponse,
    StopRecordingResponse, DemoListItem, DeleteDemoResponse,
)
from ...demonstrations.player import DemonstrationPlayer
from ...demonstrations.recorder import DemonstrationRecorder
from ...security.credentials import CredentialManager
from .device import _ctrl

router = APIRouter(prefix="/demonstrations", tags=["demonstrations"])

# active recorder sessions: recording_id -> DemonstrationRecorder
_recorders: dict[str, DemonstrationRecorder] = {}

# loaded once at import time — secrets.yaml is read from disk, never re-parsed per request
_credentials = CredentialManager()

LOCAL_DEMOS_PATH = Path(__file__).resolve().parent.parent.parent / "demonstrations_data"


def _get_recorder(recording_id: str) -> DemonstrationRecorder:
    recorder = _recorders.get(recording_id)
    if recorder is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recorder


async def _perform_action(device, action_type: str, params: dict) -> None:
    """Perform an action on the device, mirroring player.py's replay() branches."""
    try:
        if action_type == "tap":
            await device.tap(params["x"], params["y"])
        elif action_type == "text":
            await device.clear_text()
            await device.text(params["content"])
        elif action_type == "swipe":
            await device.swipe(
                params.get("direction", "up"),
                from_x=params.get("from_x"),
                from_y=params.get("from_y"),
            )
        elif action_type == "long_press":
            await device.long_press(params["x"], params["y"])
        elif action_type == "key_event":
            await device.key_event(params["code"])
        elif action_type == "wait":
            await asyncio.sleep(params.get("duration", 1))
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Missing parameter '{e.args[0]}' for action '{action_type}'",
        ) from e


@router.post("/{app_name}/record/start", response_model=StartRecordingResponse)
async def start_recording(app_name: str, body: StartRecordingRequest, request: Request):
    ctrl = _ctrl(request, body.device_serial)
    recording_id = str(uuid.uuid4())
    _recorders[recording_id] = DemonstrationRecorder(
        device=ctrl, app_name=app_name, task_description=body.task_description
    )
    return StartRecordingResponse(recording_id=recording_id)


@router.post("/{app_name}/record/step", response_model=RecordStepResponse)
async def record_step(app_name: str, body: RecordStepRequest):
    recorder = _get_recorder(body.recording_id)
    if not recorder.device.is_connected():
        raise HTTPException(status_code=503, detail="No Android device connected")
    await recorder.capture_step(body.action_type, description=body.description, **body.params)
    await _perform_action(recorder.device, body.action_type, body.params)
    return RecordStepResponse(ok=True, steps_recorded=len(recorder.steps))


@router.post("/{app_name}/record/stop", response_model=StopRecordingResponse)
async def stop_recording(app_name: str, body: StopRecordingRequest):
    recorder = _get_recorder(body.recording_id)
    path = LOCAL_DEMOS_PATH / app_name / f"{body.recording_id}.json"
    recorder.save(str(path))
    _recorders.pop(body.recording_id, None)
    return StopRecordingResponse(ok=True, path=str(path))


@router.get("/{app_name}", response_model=list[DemoListItem])
async def list_demonstrations(app_name: str):
    app_dir = LOCAL_DEMOS_PATH / app_name
    if not app_dir.is_dir():
        return []
    items = []
    for p in sorted(app_dir.glob("*.json")):
        try:
            with open(p) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        items.append(DemoListItem(
            recording_id=p.stem,
            task_description=data.get("task_description", ""),
            step_count=len(data.get("steps", [])),
            created_at=datetime.fromtimestamp(os.path.getmtime(p)).isoformat(),
        ))
    return items


@router.post("/{app_name}/{recording_id}/replay")
async def replay_demonstration(
    app_name: str, recording_id: str, body: ReplayRequest, request: Request
):
    ctrl = _ctrl(request, body.device_serial)
    path = LOCAL_DEMOS_PATH / app_name / f"{recording_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Demonstration not found")
    player = DemonstrationPlayer(device=ctrl, credentials=_credentials)
    macro_data = player.load(str(path))
    return await player.replay(macro_data, on_drift=body.on_drift)


@router.delete("/{app_name}/{recording_id}", response_model=DeleteDemoResponse)
async def delete_demonstration(app_name: str, recording_id: str):
    path = LOCAL_DEMOS_PATH / app_name / f"{recording_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Demonstration not found")
    path.unlink()
    return DeleteDemoResponse(ok=True)

from typing import Literal, Optional
from pydantic import BaseModel


# ── Device ────────────────────────────────────────────────────────────────────

class DeviceStatus(BaseModel):
    connected: bool
    serial: Optional[str] = None
    resolution: Optional[list[int]] = None  # [width, height]
    message: str = ""


class ScreenshotResponse(BaseModel):
    screenshot_b64: str


class TapRequest(BaseModel):
    x: int
    y: int


class KeyEventRequest(BaseModel):
    code: int


class OkResponse(BaseModel):
    ok: bool
    message: str = ""


# ── Agent ─────────────────────────────────────────────────────────────────────

class ExploreRequest(BaseModel):
    app_name: str
    max_rounds: int = 20
    provider: Literal["gemini", "openai", "anthropic"] = "gemini"


class DeployRequest(BaseModel):
    task: str
    app_name: str
    max_rounds: int = 30
    provider: Literal["gemini", "openai", "anthropic"] = "gemini"


class SessionResponse(BaseModel):
    session_id: str
    message: str = ""


class AgentStatusResponse(BaseModel):
    session_id: str
    status: str
    round_num: int
    task_complete: bool
    failure_reason: Optional[str] = None
    errors: list[str] = []


# ── Knowledge Base ────────────────────────────────────────────────────────────

class KBDocOut(BaseModel):
    id: str
    app_name: str
    element_sig: str
    class_name: str
    resource_id: str
    content_desc: str
    text: str
    documentation: str
    observed_result: str
    last_explored_at: str


class KBListResponse(BaseModel):
    app_name: str
    count: int
    docs: list[KBDocOut]


class KBDeleteResponse(BaseModel):
    deleted: int

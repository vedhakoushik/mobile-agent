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


class PairDeviceRequest(BaseModel):
    ip: str
    port: int
    code: str


class ConnectDeviceRequest(BaseModel):
    ip: str
    port: int


# ── Agent ─────────────────────────────────────────────────────────────────────

class ExploreRequest(BaseModel):
    app_name: str
    max_rounds: int = 20
    device_serial: Optional[str] = None
    provider: Literal["gemini", "openai", "anthropic", "ollama", "cerebras", "glm"] = "gemini"
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    max_llm_calls: Optional[int] = None


class DeployRequest(BaseModel):
    task: str
    app_name: str
    max_rounds: int = 30
    device_serial: Optional[str] = None
    provider: Literal["gemini", "openai", "anthropic", "ollama", "cerebras", "glm"] = "gemini"
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    max_llm_calls: Optional[int] = None


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
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0
    llm_call_count: int = 0


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

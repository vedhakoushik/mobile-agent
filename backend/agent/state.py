from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Literal, Optional


@dataclass
class RunConfig:
    app_name: str
    task: str
    mode: Literal["explore", "deploy"]
    provider: str = "gemini"
    max_rounds: int = 20


@dataclass
class AgentState:
    session_id: str
    config: RunConfig

    # device + KB — injected by API layer
    device: Any = None
    kb: Any = None
    ws_broadcast: Optional[Callable[..., Coroutine]] = None

    # per-round (overwritten each round)
    round_num: int = 0
    screenshot_b64: str = ""          # current annotated screenshot
    raw_screenshot: bytes = b""       # raw bytes before annotation
    elements: list[dict] = field(default_factory=list)

    # multi-agent
    sub_steps: list[str] = field(default_factory=list)
    current_step_idx: int = 0

    # running history
    action_history: list[dict] = field(default_factory=list)
    explored_elements: set[str] = field(default_factory=set)

    # control flow
    status: Literal["idle", "running", "paused", "done", "error"] = "idle"
    task_complete: bool = False
    failure_reason: Optional[str] = None
    errors: list[str] = field(default_factory=list)

    # convenience accessors
    @property
    def app_name(self) -> str:
        return self.config.app_name

    @property
    def task(self) -> str:
        return self.config.task

    @property
    def mode(self) -> str:
        return self.config.mode

    @property
    def provider(self) -> str:
        return self.config.provider

    @property
    def max_rounds(self) -> int:
        return self.config.max_rounds

    async def broadcast(self, event: dict) -> None:
        if self.ws_broadcast:
            await self.ws_broadcast(self.session_id, event)

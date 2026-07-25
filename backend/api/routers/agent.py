import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Request

from ..schemas import (
    ExploreRequest, DeployRequest,
    SessionResponse, AgentStatusResponse,
)
from ..ws.manager import ws_manager
from ...agent.loop import run_explore, run_deploy
from ...agent.state import AgentState, RunConfig
from ...knowledge_base.store import KnowledgeBase

router = APIRouter(prefix="/agent", tags=["agent"])

# active sessions: session_id -> AgentState
_sessions: dict[str, AgentState] = {}


def _make_state(session_id: str, config: RunConfig, request: Request) -> AgentState:
    device = request.app.state.device
    if device is None or not device.is_connected():
        raise HTTPException(status_code=503, detail="No Android device connected")

    kb = KnowledgeBase(app_name=config.app_name)
    state = AgentState(
        session_id=session_id,
        config=config,
        device=device,
        kb=kb,
        ws_broadcast=ws_manager.broadcast,
    )
    return state


@router.post("/explore", response_model=SessionResponse)
async def start_explore(body: ExploreRequest, request: Request):
    session_id = str(uuid.uuid4())
    config = RunConfig(
        app_name=body.app_name,
        task="explore",
        mode="explore",
        provider=body.provider,
        max_rounds=body.max_rounds,
    )
    state = _make_state(session_id, config, request)
    _sessions[session_id] = state
    asyncio.create_task(run_explore(state), name=f"explore-{session_id}")
    return SessionResponse(session_id=session_id, message="Exploration started")


@router.post("/deploy", response_model=SessionResponse)
async def start_deploy(body: DeployRequest, request: Request):
    session_id = str(uuid.uuid4())
    config = RunConfig(
        app_name=body.app_name,
        task=body.task,
        mode="deploy",
        provider=body.provider,
        max_rounds=body.max_rounds,
    )
    state = _make_state(session_id, config, request)
    _sessions[session_id] = state
    asyncio.create_task(run_deploy(state), name=f"deploy-{session_id}")
    return SessionResponse(session_id=session_id, message="Deployment started")


@router.get("/{session_id}", response_model=AgentStatusResponse)
async def get_status(session_id: str):
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return AgentStatusResponse(
        session_id=session_id,
        status=state.status,
        round_num=state.round_num,
        task_complete=state.task_complete,
        failure_reason=state.failure_reason,
        errors=state.errors[-5:],
    )


@router.delete("/{session_id}", response_model=AgentStatusResponse)
async def stop_agent(session_id: str):
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    state.status = "done"
    state.task_complete = False
    return AgentStatusResponse(
        session_id=session_id,
        status="done",
        round_num=state.round_num,
        task_complete=False,
    )

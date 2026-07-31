import asyncio
import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from ..schemas import (
    ExploreRequest, DeployRequest,
    FanoutDeployRequest, FanoutDeployResponse, FanoutSessionResult,
    SessionResponse, AgentStatusResponse, SessionHistoryEvent,
)
from ..ws.manager import ws_manager
from ...agent.loop import run_explore, run_deploy
from ...agent.state import AgentState, RunConfig
from ...knowledge_base.store import KnowledgeBase
from ...app_cards.loader import AppCardProvider
from ...security.credentials import CredentialManager
from ...graph.neo4j_client import NavigationGraph
from ...persistence import get_session, get_session_events, list_sessions

router = APIRouter(prefix="/agent", tags=["agent"])

# active sessions: session_id -> AgentState
_sessions: dict[str, AgentState] = {}

# loaded once at import time — secrets.yaml is read from disk, never re-parsed per request
_credentials = CredentialManager()

# loaded once at import time — app_cards.json + markdown files are read from disk, never re-parsed
_app_cards = AppCardProvider()

# constructed once at import time — the neo4j driver itself is lazy (no connection
# attempt happens until first record_transition/find_path call), so this never
# blocks startup even if Neo4j is down
_nav_graph = NavigationGraph()


async def _run_and_release(coro, registry, serial):
    try:
        await coro
    finally:
        registry.release(serial)


def _make_state(
    session_id: str, config: RunConfig, request: Request, device_serial: Optional[str] = None
) -> AgentState:
    registry = request.app.state.devices
    acquired = registry.acquire(device_serial)
    if acquired is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "No idle Android device available"
                if device_serial is None
                else f"Device '{device_serial}' not found or busy"
            ),
        )
    serial, device = acquired

    kb = KnowledgeBase(app_name=config.app_name)
    app_card = _app_cards.get(config.app_name)
    state = AgentState(
        session_id=session_id,
        config=config,
        device=device,
        kb=kb,
        credentials=_credentials,
        app_card=app_card,
        nav_graph=_nav_graph,
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
        max_tokens=body.max_tokens,
        max_cost_usd=body.max_cost_usd,
        max_llm_calls=body.max_llm_calls,
    )
    state = _make_state(session_id, config, request, body.device_serial)
    _sessions[session_id] = state
    asyncio.create_task(
        _run_and_release(run_explore(state), request.app.state.devices, state.device.serial),
        name=f"explore-{session_id}",
    )
    return SessionResponse(session_id=session_id, message="Exploration started")


@router.post("/deploy", response_model=SessionResponse)
async def start_deploy(body: DeployRequest, request: Request):
    session_id = str(uuid.uuid4())
    config = RunConfig(
        app_name=body.app_name,
        task=body.task,
        mode="deploy",
        provider=body.provider,
        reasoning_mode=body.reasoning_mode,
        max_rounds=body.max_rounds,
        max_tokens=body.max_tokens,
        max_cost_usd=body.max_cost_usd,
        max_llm_calls=body.max_llm_calls,
    )
    state = _make_state(session_id, config, request, body.device_serial)
    _sessions[session_id] = state
    asyncio.create_task(
        _run_and_release(run_deploy(state), request.app.state.devices, state.device.serial),
        name=f"deploy-{session_id}",
    )
    return SessionResponse(session_id=session_id, message="Deployment started")


@router.post("/deploy/fanout", response_model=FanoutDeployResponse)
async def start_deploy_fanout(body: FanoutDeployRequest, request: Request):
    registry = request.app.state.devices
    results: list[FanoutSessionResult] = []

    for serial in body.device_serials:
        acquired = registry.acquire(serial)
        if acquired is None:
            results.append(FanoutSessionResult(
                device_serial=serial,
                session_id=None,
                started=False,
                detail="not found or busy",
            ))
            continue

        acquired_serial, device = acquired
        session_id = str(uuid.uuid4())
        config = RunConfig(
            app_name=body.app_name,
            task=body.task,
            mode="deploy",
            provider=body.provider,
            reasoning_mode=body.reasoning_mode,
            max_rounds=body.max_rounds,
            max_tokens=body.max_tokens,
            max_cost_usd=body.max_cost_usd,
            max_llm_calls=body.max_llm_calls,
        )
        kb = KnowledgeBase(app_name=config.app_name)
        app_card = _app_cards.get(config.app_name)
        state = AgentState(
            session_id=session_id,
            config=config,
            device=device,
            kb=kb,
            credentials=_credentials,
            app_card=app_card,
            nav_graph=_nav_graph,
            ws_broadcast=ws_manager.broadcast,
        )
        _sessions[session_id] = state
        asyncio.create_task(
            _run_and_release(run_deploy(state), registry, acquired_serial),
            name=f"deploy-fanout-{session_id}",
        )
        results.append(FanoutSessionResult(
            device_serial=serial,
            session_id=session_id,
            started=True,
        ))

    return FanoutDeployResponse(results=results)


@router.get("/sessions")
async def list_sessions_endpoint(limit: int = 50, offset: int = 0):
    return await list_sessions(limit=limit, offset=offset)


@router.get("/{session_id}", response_model=AgentStatusResponse)
async def get_status(session_id: str):
    state = _sessions.get(session_id)
    if state is None:
        db_row = await get_session(session_id)
        if db_row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return AgentStatusResponse(
            session_id=db_row["session_id"],
            status=db_row["status"],
            round_num=db_row["round_num"],
            task_complete=bool(db_row["task_complete"]),
            failure_reason=db_row["failure_reason"],
            errors=[],
            tokens_used=db_row["tokens_used"],
            estimated_cost_usd=db_row["estimated_cost_usd"],
            llm_call_count=db_row["llm_call_count"],
            escalation_count=db_row["escalation_count"],
        )
    return AgentStatusResponse(
        session_id=session_id,
        status=state.status,
        round_num=state.round_num,
        task_complete=state.task_complete,
        failure_reason=state.failure_reason,
        errors=state.errors[-5:],
        tokens_used=state.tokens_used,
        estimated_cost_usd=state.estimated_cost_usd,
        llm_call_count=state.llm_call_count,
        escalation_count=state.escalation_count,
    )


@router.get("/{session_id}/history", response_model=list[SessionHistoryEvent])
async def get_session_history(session_id: str):
    events = await get_session_events(session_id)
    return [
        SessionHistoryEvent(
            round_num=e["round_num"],
            action=json.loads(e["action_json"]),
            element_sig=e["element_sig"],
            created_at=e["created_at"],
        )
        for e in events
    ]


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

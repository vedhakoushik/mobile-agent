"""Regression tests for three bugs found in a code audit:

1. Stop did nothing. DELETE /agent/{id} and the WebSocket "stop" message both
   set status="done", but neither loop ever checked it — they only checked
   for "paused". The agent kept driving the device while the API reported it
   as stopped.
2. _sessions grew forever. Every run added an AgentState (which holds a
   full screenshot in memory) and nothing ever removed it.
3. A device could be leaked. If building the deploy coroutine raised after
   _make_state() had already acquired the device, release() was never
   reached and that device stayed busy until restart.
"""

import asyncio

from backend.agent.loop import _should_continue
from backend.agent.state import AgentState, RunConfig


def _state(**overrides):
    config = RunConfig(app_name="youtube", task="do a thing", mode="deploy")
    state = AgentState(session_id="sess-1", config=config)
    for k, v in overrides.items():
        setattr(state, k, v)
    return state


# ── Bug 1: stop must actually stop ───────────────────────────────────────────


def test_loop_continues_under_normal_conditions():
    assert _should_continue(_state(status="running")) is True


def test_stop_requested_halts_the_loop():
    assert _should_continue(_state(status="running", stop_requested=True)) is False


def test_stop_halts_even_while_paused():
    # A paused run must still be stoppable — otherwise a paused agent that's
    # been told to stop would sit in the pause branch forever.
    assert _should_continue(_state(status="paused", stop_requested=True)) is False


def test_existing_exit_conditions_still_hold():
    assert _should_continue(_state(task_complete=True)) is False
    assert _should_continue(_state(round_num=20)) is False  # max_rounds defaults to 20


def test_paused_alone_does_not_exit_the_loop():
    # Pause is handled inside the loop body (sleep + continue), not by exiting.
    assert _should_continue(_state(status="paused")) is True


# ── Bugs 2 + 3: _run_and_release cleans up on every path ─────────────────────


class _FakeRegistry:
    def __init__(self):
        self.released = []

    def release(self, serial):
        self.released.append(serial)


def test_run_and_release_releases_device_and_drops_session():
    from backend.api.routers import agent as agent_router

    registry = _FakeRegistry()
    state = _state()
    agent_router._sessions["sess-1"] = state

    async def work():
        return None

    asyncio.run(agent_router._run_and_release(work(), registry, "serial-1", "sess-1"))

    assert registry.released == ["serial-1"]
    assert "sess-1" not in agent_router._sessions


def test_run_and_release_cleans_up_even_when_the_run_raises():
    from backend.api.routers import agent as agent_router

    registry = _FakeRegistry()
    agent_router._sessions["sess-2"] = _state()

    async def failing_work():
        raise RuntimeError("agent blew up mid-run")

    # The device must come back and the session must be dropped even on crash,
    # otherwise one bad run permanently burns a device slot.
    asyncio.run(agent_router._run_and_release(failing_work(), registry, "serial-2", "sess-2"))

    assert registry.released == ["serial-2"]
    assert "sess-2" not in agent_router._sessions

import asyncio

from backend.agent.state import AgentState, RunConfig


def _config(**overrides):
    kwargs = {"app_name": "youtube", "task": "search for cats", "mode": "explore"}
    kwargs.update(overrides)
    return RunConfig(**kwargs)


def test_run_config_defaults():
    config = _config()
    assert config.reasoning_mode == "reasoning"
    assert config.provider == "gemini"
    assert config.max_rounds == 20
    assert config.max_tokens is None
    assert config.max_cost_usd is None
    assert config.max_llm_calls is None


def test_agent_state_defaults():
    state = AgentState(session_id="sess-1", config=_config())
    assert state.device is None
    assert state.kb is None
    assert state.credentials is None
    assert state.app_card is None
    assert state.nav_graph is None
    assert state.ws_broadcast is None
    assert state.round_num == 0
    assert state.screenshot_b64 == ""
    assert state.raw_screenshot == b""
    assert state.elements == []
    assert state.last_screen_sig is None
    assert state.last_elem_sig is None
    assert state.last_action_thought == ""
    assert state.sub_steps == []
    assert state.current_step_idx == 0
    assert state.action_history == []
    assert state.explored_elements == set()
    assert state.status == "idle"
    assert state.task_complete is False
    assert state.failure_reason is None
    assert state.errors == []
    assert state.tokens_used == 0
    assert state.estimated_cost_usd == 0.0
    assert state.llm_call_count == 0
    assert state.escalation_count == 0


def test_agent_state_properties_delegate_to_config():
    state = AgentState(
        session_id="sess-1",
        config=_config(app_name="youtube", task="search for cats", mode="deploy"),
    )
    assert state.app_name == "youtube"
    assert state.task == "search for cats"
    assert state.mode == "deploy"
    assert state.provider == "gemini"
    assert state.max_rounds == 20


def test_loop_relies_on_defaults_guarding_transition_recording():
    state = AgentState(session_id="sess-1", config=_config())
    # loop.py guards record_transition with `nav_graph is not None and last_screen_sig is not None`
    assert state.nav_graph is None
    assert state.last_screen_sig is None
    # loop relies on round_num < max_rounds as the run condition
    assert state.round_num < state.max_rounds


def test_mutable_defaults_are_isolated_between_instances():
    a = AgentState(session_id="a", config=_config())
    b = AgentState(session_id="b", config=_config())
    a.action_history.append({"round": 1})
    a.explored_elements.add("sig")
    a.sub_steps.append("step")
    a.errors.append("boom")
    assert b.action_history == []
    assert b.explored_elements == set()
    assert b.sub_steps == []
    assert b.errors == []


def test_broadcast_noop_without_callback():
    state = AgentState(session_id="sess-1", config=_config())
    assert asyncio.run(state.broadcast({"type": "ping"})) is None

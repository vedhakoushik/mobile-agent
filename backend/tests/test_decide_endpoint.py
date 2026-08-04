"""Tests for POST /agent/decide — the stateless on-device decision endpoint.

The LLM call is stubbed; these cover request/response plumbing and the
failure paths, not model quality.
"""
import pytest
from fastapi.testclient import TestClient

from backend.api.routers import agent as agent_router


@pytest.fixture
def client(monkeypatch):
    # Import first: main.py calls load_dotenv() at import time, which would
    # put the real API_KEY back into the environment after we cleared it.
    from backend.api.main import app
    monkeypatch.delenv("API_KEY", raising=False)  # auth fails open when unset
    return TestClient(app)


def _stub_llm(monkeypatch, result):
    async def fake_call_text_llm(provider, prompt, trace=None):
        return result
    monkeypatch.setattr(agent_router, "call_text_llm", fake_call_text_llm)


def _body(**overrides):
    body = {
        "task": "Search for cats",
        "app_name": "youtube",
        "elements": [
            {
                "id": 1,
                "class_name": "android.widget.ImageView",
                "resource_id": "com.google.android.youtube:id/search",
                "text": "",
                "content_desc": "Search",
            }
        ],
    }
    body.update(overrides)
    return body


def test_returns_decision(client, monkeypatch):
    _stub_llm(monkeypatch, {
        "action": "tap",
        "element_id": 1,
        "thought": "tap search",
        "observation": "search visible",
        "_usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    })
    r = client.post("/api/v1/agent/decide", json=_body())
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "tap"
    assert data["element_id"] == 1
    assert data["thought"] == "tap search"
    assert data["tokens_used"] == 120


def test_no_device_required(client, monkeypatch):
    """The whole point: this must work with zero ADB devices connected."""
    _stub_llm(monkeypatch, {"action": "finish", "_usage": {}})
    r = client.post("/api/v1/agent/decide", json=_body())
    assert r.status_code == 200
    assert r.json()["action"] == "finish"


def test_history_is_accepted(client, monkeypatch):
    captured = {}

    async def fake_call_text_llm(provider, prompt, trace=None):
        captured["prompt"] = prompt
        return {"action": "text", "text_input": "cats", "_usage": {}}

    monkeypatch.setattr(agent_router, "call_text_llm", fake_call_text_llm)
    prior = {"action": "tap", "element_id": 1, "thought": "tapped search"}
    r = client.post("/api/v1/agent/decide", json=_body(
        round_num=1,
        history=[{"round": 0, "action": prior}],
    ))
    assert r.status_code == 200
    assert r.json()["text_input"] == "cats"
    # prior action must reach the prompt, or the model repeats itself forever
    assert "TAP" in captured["prompt"]


def test_elements_reach_the_prompt(client, monkeypatch):
    captured = {}

    async def fake_call_text_llm(provider, prompt, trace=None):
        captured["prompt"] = prompt
        return {"action": "tap", "element_id": 1, "_usage": {}}

    monkeypatch.setattr(agent_router, "call_text_llm", fake_call_text_llm)
    client.post("/api/v1/agent/decide", json=_body())
    assert "com.google.android.youtube:id/search" in captured["prompt"]
    assert "Search for cats" in captured["prompt"]


def test_llm_failure_is_502(client, monkeypatch):
    async def boom(provider, prompt, trace=None):
        raise RuntimeError("provider down")

    monkeypatch.setattr(agent_router, "call_text_llm", boom)
    r = client.post("/api/v1/agent/decide", json=_body())
    assert r.status_code == 502


def test_missing_action_is_502(client, monkeypatch):
    _stub_llm(monkeypatch, {"thought": "no action key", "_usage": {}})
    r = client.post("/api/v1/agent/decide", json=_body())
    assert r.status_code == 502


def test_blank_action_is_502(client, monkeypatch):
    _stub_llm(monkeypatch, {"action": "   ", "_usage": {}})
    r = client.post("/api/v1/agent/decide", json=_body())
    assert r.status_code == 502


def test_empty_elements_allowed(client, monkeypatch):
    """A blank screen is a legitimate state — the agent should be able to
    decide to swipe or go back rather than the request being rejected."""
    _stub_llm(monkeypatch, {"action": "swipe", "direction": "up", "_usage": {}})
    r = client.post("/api/v1/agent/decide", json=_body(elements=[]))
    assert r.status_code == 200
    assert r.json()["direction"] == "up"


def test_decide_not_shadowed_by_session_wildcard(client, monkeypatch):
    """/agent/{session_id} is a GET and /decide is a POST, but a regression in
    route order would still be worth catching early."""
    _stub_llm(monkeypatch, {"action": "finish", "_usage": {}})
    r = client.post("/api/v1/agent/decide", json=_body())
    assert r.status_code == 200

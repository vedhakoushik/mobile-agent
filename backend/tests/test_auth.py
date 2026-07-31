import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from security.auth import ApiKeyAuthMiddleware, verify_ws_token


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ApiKeyAuthMiddleware)

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/protected")
    async def protected():
        return {"ok": True}

    return app


@pytest.fixture
def unconfigured(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    return TestClient(_make_app())


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "correct-key")
    return TestClient(_make_app())


# ── ApiKeyAuthMiddleware ─────────────────────────────────────────────────────


def test_unconfigured_key_allows_any_request(unconfigured):
    resp = unconfigured.get("/api/v1/protected")
    assert resp.status_code == 200


def test_configured_key_rejects_missing_header(configured):
    resp = configured.get("/api/v1/protected")
    assert resp.status_code == 401


def test_configured_key_rejects_wrong_header(configured):
    resp = configured.get("/api/v1/protected", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_configured_key_accepts_correct_header(configured):
    resp = configured.get("/api/v1/protected", headers={"X-API-Key": "correct-key"})
    assert resp.status_code == 200


def test_health_path_exempt_even_when_configured(configured):
    resp = configured.get("/api/v1/health")
    assert resp.status_code == 200


def test_options_request_bypasses_auth(configured):
    resp = configured.options("/api/v1/protected")
    assert resp.status_code != 401


# ── verify_ws_token ──────────────────────────────────────────────────────────


def test_ws_token_unconfigured_always_true(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    assert verify_ws_token(None) is True
    assert verify_ws_token("anything") is True


def test_ws_token_configured_requires_match(monkeypatch):
    monkeypatch.setenv("API_KEY", "correct-key")
    assert verify_ws_token("correct-key") is True
    assert verify_ws_token("wrong-key") is False
    assert verify_ws_token(None) is False

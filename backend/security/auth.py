import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

API_KEY_HEADER = "X-API-Key"

# Routes that never require a key — liveness checks must stay reachable
# without auth, and preflight requests carry no custom headers by design.
_EXEMPT_PATHS = {"/api/v1/health"}


def _get_configured_key() -> str | None:
    key = os.environ.get("API_KEY")
    return key if key else None


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Requires X-API-Key on every HTTP request when API_KEY is configured.

    If API_KEY is unset, auth is skipped entirely (matches the same
    fail-open-with-a-loud-warning posture used for the optional Neo4j/
    Langfuse integrations) — printed once at startup in main.py, not here,
    so this stays a pure request-time check with no import-time side effects.
    """

    async def dispatch(self, request: Request, call_next):
        configured_key = _get_configured_key()
        if configured_key is None:
            return await call_next(request)

        if request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        provided = request.headers.get(API_KEY_HEADER)
        if provided is None or not secrets.compare_digest(provided, configured_key):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid API key"})

        return await call_next(request)


def verify_ws_token(token: str | None) -> bool:
    """WebSocket handshakes can't carry custom headers from browser JS, so the
    key travels as a query param instead (?token=...). Same fail-open-when-
    unconfigured posture as the HTTP middleware."""
    configured_key = _get_configured_key()
    if configured_key is None:
        return True
    if token is None:
        return False
    return secrets.compare_digest(token, configured_key)

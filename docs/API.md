# API Reference

Base URL (local dev): `http://localhost:8000/api/v1`
Base URL (Docker Compose, via nginx): `http://localhost/api/v1`

All request/response bodies are JSON. There is no authentication layer — do not expose this
backend beyond a trusted local network without adding one (see
[CONTRIBUTING.md](../CONTRIBUTING.md)). This matters more than it used to: the backend now also
holds a credential vault (`secrets.yaml`) that any caller with API access can trigger a `type_secret`
action against, even though the *value* itself never leaves the server.

## Health

### `GET /api/v1/health`
Liveness check.

```json
{ "status": "ok" }
```

## Device

Backed by `backend/api/routers/device.py`, `app.state.devices` is a `DeviceRegistry`
(`backend/device/registry.py`) managing possibly multiple connected devices. Every endpoint below
accepts an optional `?serial=<serial>` query param to target a specific device; omitting it falls
back to the first connected device.

### `GET /api/v1/device/list`
All connected devices and their busy state (busy = currently acquired by a running session).
```json
[
  { "serial": "emulator-5554", "resolution": [1080, 2400], "busy": false },
  { "serial": "192.168.1.5:5555", "resolution": [1440, 3120], "busy": true }
]
```

### `GET /api/v1/device/status?serial=<optional>`
```json
{
  "connected": true,
  "serial": "emulator-5554",
  "resolution": [1080, 2340],
  "message": "Connected"
}
```

### `GET /api/v1/device/screenshot?serial=<optional>`
Raw current screenshot (not annotated — annotated screenshots come over the agent WebSocket).
```json
{ "screenshot_b64": "iVBORw0KGgoAAAANS..." }
```

### `POST /api/v1/device/tap?serial=<optional>`
```json
// request
{ "x": 540, "y": 1200 }
// response
{ "ok": true, "message": "" }
```

### `POST /api/v1/device/keyevent?serial=<optional>`
Sends a raw Android keycode (e.g. `4` = back, `3` = home, `66` = enter, `67` = delete —
see `backend/device/controller.py`).
```json
// request
{ "code": 4 }
// response
{ "ok": true, "message": "" }
```

### `POST /api/v1/device/pair`
Android 11+ Wireless Debugging pairing step (shells out to `adb pair` — needs `adb` on the
backend process's `PATH`). Uses the pairing `ip:port` + 6-digit code shown on the phone's
"Pair device with pairing code" screen — **not** the same port used for `/device/connect`.
```json
// request
{ "ip": "192.168.1.5", "port": 41235, "code": "123456" }
// response — 200
{ "paired": true, "message": "Successfully paired to 192.168.1.5:41235 [guid=...]\n — now call /device/connect with the OTHER ip:port shown on the phone's Wireless debugging screen ..." }
// response — 502 on failure (wrong code, expired, network issue)
{ "detail": "error: protocol fault (couldn't read status message): No error" }
```

### `POST /api/v1/device/connect`
Connects to an already-paired (or `adb tcpip`-bootstrapped) device at a given `ip:port` — the
main Wireless Debugging screen's `ip:port`, distinct from the pairing one. On success, re-runs
device discovery and returns the updated device list.
```json
// request
{ "ip": "192.168.1.5", "port": 5555 }
// response — 200, same shape as GET /device/list
[{ "serial": "192.168.1.5:5555", "resolution": [1440, 3120], "busy": false }]
// response — 502 on failure
{ "detail": "cannot connect to 192.168.1.5:5555: ..." }
```

## Agent

Backed by `backend/api/routers/agent.py`. Starting a run returns immediately with a
`session_id`; the run itself executes as a background asyncio task and is followed via the
[WebSocket](#websocket-ws-session_id) or by polling status.

### `POST /api/v1/agent/explore`
Starts Explore mode: systematically interacts with UI elements and builds the knowledge base.
```json
// request
{
  "app_name": "linkedin",
  "max_rounds": 20,
  "provider": "gemini",        // gemini | openai | anthropic | ollama | cerebras | glm
  "device_serial": null,       // optional — target a specific device; omit to auto-pick any idle one
  "max_tokens": null,          // optional — stop the run once total tokens reach this
  "max_cost_usd": null,        // optional — stop once estimated cost (llm/pricing.py) reaches this
  "max_llm_calls": null        // optional — stop after this many LLM calls
}
// response — 200
{ "session_id": "b3f1...-uuid", "message": "Exploration started" }
// response — 503 if no idle device available
{ "detail": "No idle Android device available" }
// response — 503 if a specific device_serial was requested but not found/busy
{ "detail": "Device 'emulator-5554' not found or busy" }
```

### `POST /api/v1/agent/deploy`
Starts Deploy mode: decomposes `task` into sub-steps and executes them. Accepts the same
`device_serial` / `max_tokens` / `max_cost_usd` / `max_llm_calls` fields as `/explore` above.
```json
// request
{
  "task": "Search for Python developer roles",
  "app_name": "linkedin",
  "max_rounds": 30,
  "provider": "gemini",
  "max_llm_calls": 25
}
// response
{ "session_id": "b3f1...-uuid", "message": "Deployment started" }
```

### `GET /api/v1/agent/{session_id}`
Poll current status of a run (also used by `scripts/run_benchmark.py`).
```json
{
  "session_id": "b3f1...-uuid",
  "status": "running",           // idle | running | paused | done | error
  "round_num": 4,
  "task_complete": false,
  "failure_reason": null,        // e.g. "Usage limit reached (tokens=5305, cost=$0.0000, calls=1)" if a limit stopped it
  "errors": [],                   // last 5 error strings, if any
  "tokens_used": 5305,
  "estimated_cost_usd": 0.0,
  "llm_call_count": 1
}
```
`404` if the session ID is unknown (never started, or process restarted since). A device acquired
by this session (see `device_serial` above) is released automatically once the run reaches a
terminal state, regardless of whether it finished, errored, or hit a usage limit.

### `DELETE /api/v1/agent/{session_id}`
Requests a stop. Sets `status` to `"done"`; the loop's next iteration checks `state.status` and
exits. Note this does **not** immediately kill the background task — there can be a short delay
of up to one round.
```json
{ "session_id": "b3f1...-uuid", "status": "done", "round_num": 4, "task_complete": false }
```

## Knowledge Base

Backed by `backend/api/routers/kb.py`. All endpoints operate on one app's namespace.

### `GET /api/v1/kb/{app_name}`
Returns every stored element doc for the app.
```json
{
  "app_name": "linkedin",
  "count": 12,
  "docs": [
    {
      "id": "linkedin::com.linkedin:id/search_btn::android.widget.ImageButton",
      "app_name": "linkedin",
      "element_sig": "com.linkedin:id/search_btn::android.widget.ImageButton",
      "class_name": "android.widget.ImageButton",
      "resource_id": "com.linkedin:id/search_btn",
      "content_desc": "Search jobs",
      "text": "",
      "documentation": "Opens the job search screen with a text input and filters.",
      "observed_result": "Navigated to the search screen.",
      "last_explored_at": "2026-07-20T10:03:11.482Z"
    }
  ]
}
```

### `GET /api/v1/kb/{app_name}/search?q=<query>`
Substring filter over `documentation` and `element_sig` (case-insensitive). Empty or missing `q`
returns everything, identical to the plain list endpoint — this is not a semantic/vector search
(that only happens internally, per-round, in `retrieve_context()`).

### `DELETE /api/v1/kb/{app_name}`
Deletes all docs for the app.
```json
{ "deleted": 12 }
```

## WebSocket: `/ws/{session_id}`

Connect after starting a session to receive live events and to send control messages. Note the
WebSocket route is mounted at the app root (`/ws/{session_id}`), **not** under `/api/v1`.

- Local dev (Vite): `ws://localhost:5173/ws/{session_id}` (proxied to the backend)
- Docker Compose (nginx): `ws://localhost/ws/{session_id}`

### Client → server messages
```json
{ "type": "stop" }     // sets session status to "done"
{ "type": "pause" }    // sets status to "paused"; loop sleeps in 0.5s ticks until resumed
{ "type": "resume" }   // sets status back to "running"
```

### Server → client events
All events share a `type` discriminator (see `frontend/src/api/websocket.ts` for the TypeScript
union).

| `type` | Fields | Sent when |
|---|---|---|
| `status_change` | `status`, `mode?`, `task_complete?`, `failure_reason?`, `kb_count?` | Run starts, finishes, or errors |
| `screenshot_update` | `screenshot` (base64 PNG, annotated), `round`, `element_count` | Every round, after capture + annotation |
| `action_event` | `round`, `action`, `element_id`, `thought`, `observation` | Every round, after the LLM decision |
| `plan_ready` | `steps` (string list) | Once, at the start of a Deploy run, after planning |
| `kb_update` | `doc: {id, documentation, element_sig, app_name}` | Explore mode only, when a new element is reflected on |
| `error` | `message` | An unrecoverable exception in the loop |

Example `action_event`:
```json
{
  "type": "action_event",
  "round": 3,
  "action": "tap",
  "element_id": 7,
  "thought": "The search icon should open the job search flow.",
  "observation": "Home feed is showing with a search icon in the top bar."
}
```

`action` can be `tap | text | swipe | long_press | grid | type_secret | finish`. For
`type_secret`, the underlying decision also carries a `secret_id` (a credential *name*, e.g.
`"YOUTUBE_PASSWORD"`) — note it is intentionally **not** included in this broadcast event or in
`action_event`'s fields above, only `action`/`element_id`/`thought`/`observation` are ever sent
over the wire, same as every other action type.

There is no message replay on reconnect — a client that disconnects mid-run misses every event
broadcast in the gap (see [ARCHITECTURE.md](ARCHITECTURE.md#real-time-updates)).

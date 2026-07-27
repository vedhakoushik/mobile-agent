# Architecture

## Context and goals

Mobile Agent drives a real Android app the same way a human would: it never touches the app's
source or an accessibility API contract — only what's visible in a screenshot and what
`uiautomator` reports about the current view hierarchy. That constraint is deliberate: the same
agent should work against any installed app without per-app integration work.

Two goals shape the design:

1. **Learn once, act many times.** Explore mode's per-element documentation (the knowledge base)
   is meant to make later Deploy runs faster and more reliable, and to transfer semantically
   between similar apps (a "Search" button behaves similarly across apps, so its embedding
   should retrieve useful context even in an app never explored before).
2. **Provider-agnostic reasoning.** The LLM call is abstracted behind one interface
   (`backend/llm/vision.py`) so the reasoning model can be swapped — cloud vision models for
   quality, a local Ollama model for cost/privacy, Cerebras for fast text-only planning — without
   touching the agent loop.

## High-level design

```
Android device/emulator
        │  screencap -p / uiautomator dump  (backend/device/controller.py)
        ▼
Perception layer  (backend/perception/)
  xml_parser.py   — uiautomator XML → list[InteractiveElement] (clickable/focusable/scrollable,
                     deduped by bounds, numbered top-to-bottom/left-to-right)
  annotator.py    — draws numbered orange boxes on the screenshot so the LLM can refer to
                     elements by integer ID instead of pixel coordinates
  grid.py         — fallback: overlays a 9×9 lettered/numbered grid (A1..I9) for the rare case
                     where the target isn't a recognized interactive element
        ▼
Agent loop  (backend/agent/loop.py — run_explore / run_deploy)
  1. capture screenshot + XML
  2. parse + annotate
  3. retrieve KB context for visible elements  (knowledge_base/store.py)
  4. call the vision LLM with the annotated screenshot + prompt → decision JSON
  5. execute the decided action  (agent/executor.py → device/controller.py)
  6. wait for the UI to settle
  7. (Explore only) reflect on novel elements → write a new KB doc  (agent/reflector.py)
  8. broadcast every step over WebSocket  (api/ws/manager.py)
        ▼
React dashboard  (frontend/) — live screenshot, action log, plan progress, KB browser
```

## Agent loop: Explore vs. Deploy

Both modes share the capture → parse → annotate → decide → execute → settle cycle
(`backend/agent/loop.py`). They diverge in what drives the LLM's decision and when they stop:

**Explore** (`run_explore`)
- No user task — the system prompt (`EXPLORE_SYSTEM` in `llm/prompts.py`) instructs the model to
  prefer elements marked `is_novel_element: true` and to finish only once it believes the
  reachable UI is fully documented.
- After each action, `run_reflector` compares before/after screenshots of the same element with a
  second (dual-image) LLM call and writes an `ElementDoc` to the KB — a factual description of
  what the element does and what visibly changed.
- Bounded by `max_rounds` (default 20) as a hard stop regardless of completion.

**Deploy** (`run_deploy`)
- Starts with a **planner** call (`agent/planner.py`, text-only LLM) that decomposes the natural
  language task into 3–8 ordered sub-steps, broadcast to the frontend as `plan_ready`.
- Each round's prompt includes the current sub-step, the full plan with completion markers, and
  compressed action history (first + last 5 rounds) so the model has continuity without an
  unbounded context.
- `_should_advance()` is a heuristic — it scans the model's own `thought`/`observation` text for
  signal words ("submitted", "searching", "confirmed", etc.) to decide whether to advance the
  sub-step pointer. There's no ground-truth signal that a sub-step actually completed; this is a
  known soft spot — see [Trade-offs](#key-decisions-and-trade-offs).
- Every 5 rounds, a separate lightweight vision call (`build_progress_prompt`) asks "is the task
  done yet?" independent of the step heuristic, as a second check.
- Bounded by `max_rounds` (default 30).

State for a single run lives in `AgentState` (`backend/agent/state.py`) — one instance per
session, held in-memory in `api/routers/agent.py`'s `_sessions` dict, keyed by a UUID
`session_id`. There is no persistence across process restarts: an in-flight session is lost if
the backend restarts.

## Knowledge base

`backend/knowledge_base/store.py` wraps a ChromaDB collection (`mobile_agent_kb`), one collection
shared across all apps but partitioned by an `app_name` metadata filter. Each `ElementDoc` embeds
a text blob of `class_name + resource_id + text + content_desc + documentation + observed_result`
— identity fields are included alongside the generated documentation so semantically similar
elements (e.g. two different apps' search buttons) retrieve each other via cosine similarity,
which is the mechanism behind "transfer" between apps mentioned in the frontend's Setup page copy.

`retrieve_context()` queries per visible element (top 2 matches each) and is called every round in
both modes — this is the main per-round cost driver against ChromaDB and worth watching if KB size
grows large.

Storage is either a local `PersistentClient` (default, writes to `./kb_data`) or a remote
`HttpClient` when `CHROMA_HOST` is set — Docker Compose uses the latter, pointing at the
`chromadb` service.

## Multi-provider LLM layer

`backend/llm/vision.py` exposes three entry points — `call_vision_llm`, `call_dual_vision_llm`,
`call_text_llm` — each dispatching on a `provider` string (`gemini | openai | anthropic | ollama |
cerebras | glm`). Every provider function independently imports its SDK, builds the request, and
runs `_parse_json()` on the response text (which strips markdown code fences before
`json.loads`). There is no shared retry/timeout/backoff logic across providers — a transient
failure from any provider bubbles up as a raw exception to the caller in `agent/loop.py`, which
catches it, appends to `state.errors`, and continues to the next round.

Provider capability notes worth knowing before switching:
- **Cerebras has no vision model** — `_cerebras_vision`/`_cerebras_dual_vision` raise immediately.
  It's only useful for the (text-only) planner call.
- **Anthropic and Cerebras have no dual-vision (before/after) implementation** —
  `call_dual_vision_llm` falls back to `call_vision_llm` with just the "after" image, so the
  reflector's documentation quality is weaker on those providers (the model can't literally see
  what changed).
- Response format enforcement (JSON mode) is provider-specific: Gemini and OpenAI use structured
  response settings; Anthropic and the OpenAI-compatible providers (Ollama, Cerebras, GLM) rely on
  the prompt telling the model to respond with JSON only, which is inherently less reliable.

## Credential vault (`type_secret`)

`backend/security/credentials.py`'s `CredentialManager` loads named secrets from a gitignored
`secrets.yaml` at repo root (template: `secrets.example.yaml`). The LLM never sees a resolved
value — its action schema exposes a `secret_id` (a name, e.g. `"YOUTUBE_PASSWORD"`) and the
`type_secret` action, and only `backend/agent/executor.py`'s `type_secret` branch ever calls
`credentials.resolve(secret_id)`, immediately passing the raw value to `device.text()` and
discarding it — it's never assigned into `decision`, `state.action_history`, or any WebSocket
broadcast. `DEPLOY_SYSTEM`/`EXPLORE_SYSTEM` in `llm/prompts.py` explicitly instruct the model to
use `type_secret` instead of guessing/fabricating credentials via the plain `text` action.

## App cards

`backend/app_cards/loader.py`'s `AppCardProvider` loads static, hand-written markdown guidance
per app from `app_cards/app_cards.json` (maps `app_name` → filename) + the referenced `.md` files.
Injected into both `build_explore_prompt` and `build_deploy_prompt` as an `APP GUIDE:` section,
ahead of the live per-round element list — static background context the model doesn't have to
rediscover every run. Falls back to `"(no guide available for this app — explore to learn it)"`
when no card exists for the current `app_name`. Unlike the knowledge base, app cards cost zero
LLM rounds to produce — they're written once by a human, not learned via Explore mode.

## Multi-device registry

`backend/device/registry.py`'s `DeviceRegistry` replaces the old single-global-device pattern.
`discover_and_connect()` connects to every serial `adbutils` currently sees (USB or already
wireless-connected) and is called once at FastAPI startup (`api/main.py`'s `lifespan`, stored as
`app.state.devices`). Each Explore/Deploy request can pass `device_serial` (schemas.py) to target
a specific device, or omit it to auto-acquire any idle one; `registry.acquire()`/`.release()`
track busy state so two sessions can never be assigned the same device. Sessions release their
device automatically on completion via a wrapper (`_run_and_release` in `api/routers/agent.py`)
regardless of success/failure/exception.

**Wireless ADB** (`backend/device/wireless.py`) — `adbutils` has no native pairing support for
Android 11+'s Wireless Debugging flow, so `pair_device()`/`connect_device()` shell out to the
`adb pair`/`adb connect` CLI directly via subprocess, then trigger `discover_and_connect()` to
pick up the newly-visible serial (which looks like `"ip:port"` rather than a USB serial string).
Exposed as `POST /device/pair` and `POST /device/connect`.

## Usage tracking and limits

Every provider helper in `llm/vision.py` attaches a reserved `_usage` key to its returned dict
(`{"prompt_tokens", "completion_tokens", "total_tokens"}`), extracted from each provider's raw
response — Gemini's REST `usageMetadata`, the OpenAI SDK's `.usage` (used by openai/ollama/
cerebras/glm), Anthropic's `.usage.input_tokens`/`.output_tokens`. `agent/loop.py` pops this key
each round, accumulates it on `AgentState` (`tokens_used`, `estimated_cost_usd`,
`llm_call_count`), and — if `RunConfig.max_tokens`/`max_cost_usd`/`max_llm_calls` is set — stops
the run with `failure_reason = "Usage limit reached (...)"` the round a limit is hit. Cost is
computed via `llm/pricing.py`'s static $/1M-token table, which is explicitly approximate
(override via env vars) — free/local providers (Ollama) are hardcoded to $0.

## Perception details worth knowing

- **Element numbering is not stable across rounds.** IDs are reassigned every round from a fresh
  sort of currently-visible elements (top-to-bottom, left-to-right) — element `[5]` this round is
  not necessarily the same UI element as `[5]` last round. `element_sig`
  (`resource_id::class_name`) is the stable identity used for KB docs and dedup, not the numeric ID.
- **Screenshots are downscaled to 1080px width** before annotation to reduce vision-model token
  cost (`perception/annotator.py`, `MAX_WIDTH`), and bounding boxes are scaled to match.
- **Grid mode** is a fallback path, not the default — it's invoked explicitly when the model's
  `action` is `"grid"`, and costs an extra LLM round-trip (one call to pick a cell) on top of the
  original decision call.

## Real-time updates

`api/ws/manager.py`'s `WSManager` keeps an in-memory `dict[session_id, list[WebSocket]]` — no
message queue or persistence. The frontend's `AgentWebSocket` (`frontend/src/api/websocket.ts`)
auto-reconnects on close with a fixed 2s delay, but there's no message replay: if the frontend
disconnects mid-run, it will resume receiving from the next broadcast, having missed everything in
between. `agentStore.ts` holds only the last screenshot, not history, so a missed
`screenshot_update` isn't recoverable — only the derived `logEntries`/`kbDocs` arrays accumulate.

## Key decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| Screenshot + uiautomator XML instead of an accessibility service or per-app SDK | Works on any installed app with zero integration | No semantic accessibility tree — relies on the LLM's visual reasoning, which is slower and costlier per action than a native testing framework |
| In-memory session state (`_sessions` dict) | Simplest possible implementation for a single-backend-instance dev tool | No horizontal scaling, no crash recovery — a backend restart silently drops all running sessions |
| Heuristic sub-step advancement (`_should_advance`) | Avoids an extra LLM call every round just to check plan progress | Keyword matching against the model's own free-text `thought` is brittle — a model phrasing progress differently won't advance the plan pointer, so the periodic progress-check call (every 5 rounds) is the actual safety net |
| One shared ChromaDB collection filtered by `app_name` metadata rather than one collection per app | Simpler operationally, single index to manage | Every query pays the metadata filter cost, and a mistake in the `app_name` filter would leak cross-app context |
| Gemini has retry-with-backoff on 429 (`_gemini_request`); other providers don't | Gemini's free tier is what this project is tested against most, so it's the one that needed it | A rate limit or transient network error on any other provider still ends the round rather than retrying — and even Gemini's backoff (5s/15s/30s) doesn't outlast a truly exhausted daily/per-minute quota, which happened repeatedly during real testing |

## Extending the system

- **New LLM provider**: add `_<provider>_vision` / `_dual_vision` / `_text` functions in
  `backend/llm/vision.py`, add the dispatch branch in the three `call_*` functions, and add the
  provider name to the `Literal[...]` in `backend/api/schemas.py` (`ExploreRequest.provider`,
  `DeployRequest.provider`) so the API validates it.
- **New device action type**: add a branch in `backend/agent/executor.py`'s `execute_action`,
  add the action name to the schema description strings in `backend/llm/prompts.py`
  (`_EXPLORE_SCHEMA`, `_DEPLOY_SCHEMA`), and implement the underlying gesture in
  `backend/device/controller.py` if it doesn't already exist.
- **New WebSocket event type**: add the TypeScript interface in
  `frontend/src/api/websocket.ts`'s `AgentEvent` union, handle it in
  `frontend/src/hooks/useAgentStream.ts`'s switch statement, and broadcast it from the relevant
  point in `backend/agent/loop.py`.
- **New app card**: add an entry to `app_cards/app_cards.json` (`{"app_name": "filename.md"}`)
  and write the markdown file in `app_cards/` — no code changes needed, `AppCardProvider` picks it
  up on next backend start.
- **New credential**: add it to `secrets.yaml` (never commit this file — see
  `secrets.example.yaml` for the format) under a descriptive `secret_id`; it becomes available to
  the model as soon as the backend restarts and reloads `CredentialManager`.

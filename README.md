# Mobile Agent

![CI](https://github.com/vedhakoushik/mobile-agent/actions/workflows/ci.yml/badge.svg)

An autonomous agent that operates Android apps the way a person would — by looking at the
screen, deciding what to tap, and learning from what happens. It has two modes:

- **Explore** — systematically taps through an app's UI, screenshot by screenshot, and writes
  what it learns about each element into a knowledge base (KB).
- **Deploy** — given a task in plain English (e.g. *"Search for Python developer roles"*), it
  plans a sequence of sub-steps and drives the app to complete them, using the KB built during
  Explore to move faster and more reliably.

The agent talks to a real device or emulator over ADB, reasons with a vision-capable LLM
(Gemini, GPT-4o, Claude, GLM, Cerebras, or a local Ollama model), and streams its progress live to
a React dashboard over WebSocket.

Also supports **multiple devices at once** (USB or wireless ADB, with a fan-out endpoint to run
one task across several devices concurrently), a **credential vault** for typing passwords without
ever exposing the value to the LLM, hand-written **app cards** for instant per-app guidance without
exploring first, a **usage limiter** to cap a run by token count, cost, or call count, a **dual
reasoning/fast mode** for Deploy (skip the vision call when a text-only pass over the element list
is enough), a **Neo4j navigation graph** that Explore mode builds up as it runs, **human
demonstration recording/replay** with state-drift detection, and optional **Langfuse** tracing.
There's also an experimental [LlamaIndex Workflows](https://pypi.org/project/llama-index-workflows/)
port of the Deploy loop (`backend/agent/deploy_workflow.py`) — typed events, not yet wired into the
API.

Inspired by AppAgent, DroidRun, and MobileAgent. See
[docs/COMPARISON.md](docs/COMPARISON.md) for an honest look at how this stacks up against those —
including where it's weaker. See **[Known Issues and Limitations](#known-issues-and-limitations)** for
current constraints and unverified areas.

## How it works, in one picture

```
 ┌──────────────┐   screenshot + UI tree   ┌──────────────────┐
 │  Android     │ ───────────────────────► │  Perception       │
 │  device/     │                          │  (parse +         │
 │  emulator    │ ◄─────────────────────── │   annotate)       │
 └──────────────┘   tap / type / swipe     └────────┬──────────┘
                                                     │ annotated screenshot
                                                     ▼
 ┌──────────────┐   docs for visible       ┌──────────────────┐
 │  Knowledge   │ ◄─────────────────────── │  Agent loop        │
 │  Base        │   elements               │  (planner /         │
 │  (ChromaDB)  │ ───────────────────────► │   vision LLM /       │
 └──────────────┘   element behavior docs  │   reflector)         │
                                            └────────┬──────────┘
                                                     │ WebSocket events
                                                     ▼
                                            ┌──────────────────┐
                                            │  React dashboard   │
                                            └──────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full breakdown of each stage.

## Quick start

Prerequisites: Python 3.11+, Node 20+, an Android emulator or device reachable via `adb devices`,
and an API key for at least one LLM provider.

```bash
git clone https://github.com/vedhakoushik/mobile-agent.git
cd mobile-agent
cp .env.example .env        # then fill in your LLM API key

# backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, confirm the device shows as connected on the **Setup** page, then
run **Explore** on an app before trying **Deploy** — Deploy quality depends heavily on what
Explore has already documented.

Full setup instructions (emulator bootstrap, Docker Compose, environment variables) are in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Known Issues and Limitations
The project is functional, but several parts are still experimental or have environment-specific limitations.

- **Gemini free-tier quota:** The Gemini free tier allows 20 requests per day per Google Cloud project. Each agent round consumes one request, so multi-round tasks can exhaust the quota quickly. Creating another API key in the same project does not increase the quota. A `429 RESOURCE_EXHAUSTED` response indicates quota exhaustion, not an agent failure. Use a different provider or a local Ollama model when the quota is exhausted.

- **Android build requires Android Studio:** The `android/` module does not currently include a Gradle wrapper. To build the Android app, open `android/` as its own Android Studio project and use Android Studio's bundled Gradle/JDK setup.

- **End-to-end mobile/cloud path is not verified:** The phone → Tailscale → EC2 → phone path has not been verified end to end. `OnDeviceAgentLoop` has also not been verified completing a real multi-round task on physical hardware. The ADB-based laptop path is the verified execution path.

- **Navigation graph benefit is unmeasured:** Neo4j is optional and fail-soft, but the project has not yet measured whether feeding known navigation transitions into the agent actually reduces the number of rounds required. See [Issue #7](https://github.com/vedhakoushik/mobile-agent/issues/7).

- **Device actions include fixed settling delays:** The device layer currently uses fixed sleeps after actions, including about 0.8 seconds after each tap. These delays are intended to allow the UI to settle but can add significant latency. See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) and [Issue #3](https://github.com/vedhakoushik/mobile-agent/issues/3).

- **Backend authentication fails open without `API_KEY`:** If `API_KEY` is unset, authentication is currently disabled. This is convenient for local development but unsafe for an exposed backend. Do not expose the backend without configuring `API_KEY`. See [Issue #1](https://github.com/vedhakoushik/mobile-agent/issues/1).

- **Phone-to-laptop networking can be fragile:** Shared Wi-Fi networks with client isolation or CGNAT `100.x` addresses may prevent a phone from reaching the laptop. A mobile hotspot can work around this. On Windows, the firewall may also block inbound connections when the network profile is set to Public.

## Project layout

```
backend/
  agent/        explore/deploy loop, planner, executor, reflector, session state
  api/          FastAPI app, REST routers, WebSocket manager, request/response schemas
  device/       ADB device controller, multi-device registry, wireless pairing
  perception/   uiautomator XML parsing, screenshot annotation, grid-tap fallback
  llm/          multi-provider vision/text LLM client, prompt templates, cost estimation
  knowledge_base/  ChromaDB-backed per-app element documentation store
  security/     credential vault (type_secret) — LLM never sees resolved values
  app_cards/    loader for static per-app guidance markdown files
  tests/        pytest unit tests for perception
app_cards/      the actual per-app guidance .md files + app_cards.json mapping
scripts/
  setup_emulator.sh   creates and boots a headless AVD
  run_benchmark.py    scripted deploy-mode benchmark (TSR / CE / KUR metrics)
frontend/
  src/pages/    Setup, Explore, Deploy, Knowledge Base screens
  src/store/    Zustand store for session/device/log state
  src/api/      REST client + WebSocket event client
secrets.example.yaml   template for secrets.yaml (gitignored) — see docs/DEVELOPMENT.md
```

## Security testing — real evidence, not aspirational

This agent takes real physical actions on a device, so the stakes for a prompt
injection are higher than a search/compare tool: on-screen text from a malicious or
compromised app can try to steer a *real* tap/type action, not just a wrong answer.

```bash
cd backend && source venv/Scripts/activate
pytest tests/test_redact.py tests/test_risk_policy.py tests/test_prompts.py -v
ruff check backend/
```

**A real vulnerability found and fixed this session:** `classify_action()`
(`security/risk_policy.py`) classified `type_secret` as `"low"` risk — meaning it
auto-executed with **zero human confirmation** — on the reasoning that "the secret
value never reaches the LLM." True, but the *element the secret gets typed into* is
chosen by the LLM reading raw, unsanitized on-screen text
(`llm/prompts.py::_elements_txt`). A malicious screen (a phishing overlay, a hijacked
webview) could plant text aimed at steering that choice onto an attacker-controlled
field — the real credential would then get typed there with no human ever seeing it
happen. Fixed: `type_secret` now requires confirmation like any other risky action
(`test_risk_policy.py::test_type_secret_requires_confirmation_element_choice_is_llm_controlled`).

**Defense in depth added** (`backend/security/redact.py`):
- `sanitize_screen_text()` filters injection-shaped phrasing ("ignore previous
  instructions", "use type_secret", etc.) out of live element text/content-desc
  *and* out of KB docs retrieved back into a prompt — before either reaches the LLM.
  PII is deliberately **not** stripped here: legitimate element text routinely
  contains the contact/number the user is trying to interact with, and the agent
  needs to read it to function.
- `redact_pii()` strips emails/phone/card numbers from KB documentation *before* it's
  written to ChromaDB (`knowledge_base/store.py::_build_document`) — a screenshot
  reflected on during Explore can be a real app (messaging, email) and the
  documentation-writing LLM call can otherwise echo what it saw into a doc that
  outlives the session and gets retrieved into *other* sessions' prompts later.

Verified: `test_elements_txt_filters_injection_from_screen_text` and
`test_deploy_prompt_filters_injection_in_docs_context` construct a poisoned element/KB
doc and assert the built prompt string never contains the injected instruction.

**Existing self-correction / reliability mechanisms** (not new — verified, not built
from scratch):
- `agent/confirmation.py::gate_action` — pauses for human approval on medium+ risk
  actions, re-checks the screen hasn't changed while waiting (stale-decision guard),
  stops the whole run on an unattended timeout rather than guessing.
- `backend/eval/` — `run_benchmark.py` / `run_llm_quality.py` score real deploy-mode
  runs against benchmark tasks (TSR/CE/KUR metrics, see `docs/COMPARISON.md`).

**Known gap, stated plainly:** `sanitize_screen_text`'s injection patterns are a
fixed list, not exhaustive — a sufficiently novel phrasing could still get through.
The confirmation gate (`gate_action`) is the real backstop for anything risk-tiered
medium+; the gap that matters is specifically an injection that both evades the
pattern filter *and* targets a `tap`/`text` action the risk policy scores `"low"`
(an unlabeled, non-hotzone element with no dangerous keyword) — narrow, but real.

## Documentation

| Doc | Covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data flow, key decisions and trade-offs |
| [docs/API.md](docs/API.md) | REST endpoints and WebSocket event protocol |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local setup, emulator bootstrap, Docker Compose, testing, benchmarking |
| [docs/COMPARISON.md](docs/COMPARISON.md) | Honest comparison against DroidRun/AppAgent/Mobile-Agent with real benchmark numbers |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Code style, PR process, how to add an LLM provider |

## License

No license file is currently included — treat this as all-rights-reserved until one is added.

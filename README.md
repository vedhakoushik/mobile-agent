# Mobile Agent

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

Also supports **multiple devices at once** (USB or wireless ADB), a **credential vault** for
typing passwords without ever exposing the value to the LLM, hand-written **app cards** for
instant per-app guidance without exploring first, and a **usage limiter** to cap a run by token
count, cost, or call count.

Inspired by AppAgent, DroidRun, and MobileAgent. See
[docs/COMPARISON.md](docs/COMPARISON.md) for an honest look at how this stacks up against those —
including where it's weaker.

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

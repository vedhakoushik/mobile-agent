# Development Guide

## Prerequisites

- Python 3.11+
- Node 20+
- Android SDK `platform-tools` (for `adb`) — and `cmdline-tools` + `emulator` if you want to boot
  a local AVD via `scripts/setup_emulator.sh`
- An Android emulator or physical device reachable via `adb devices`
- At least one LLM provider API key (see [Choosing a provider](#choosing-a-provider))
- Docker + Docker Compose, only if you want the containerized path

## Environment variables

Copy `.env.example` to `.env` and fill in what you need:

| Variable | Required | Notes |
|---|---|---|
| `LLM_PROVIDER` | yes | `gemini` \| `openai` \| `anthropic` \| `ollama` \| `cerebras` \| `glm` |
| `GEMINI_API_KEY` | if using gemini | from Google AI Studio |
| `OPENAI_API_KEY` | if using openai | |
| `ANTHROPIC_API_KEY` | if using anthropic | |
| `OLLAMA_BASE_URL` | if using ollama | default `http://localhost:11434` |
| `OLLAMA_VISION_MODEL` / `OLLAMA_TEXT_MODEL` | no | defaults `qwen2.5vl` / `qwen2.5:7b` — pull with `ollama pull <model>` first |
| `CEREBRAS_API_KEY` / `CEREBRAS_MODEL` | if using cerebras | text-only, no vision — see [ARCHITECTURE.md](ARCHITECTURE.md#multi-provider-llm-layer) |
| `GLM_API_KEY` / `GLM_VISION_MODEL` / `GLM_TEXT_MODEL` | if using glm | Zhipu AI, free tier available, has vision |
| `ANDROID_SERIAL` | no, mostly unused now | the backend now discovers and connects to **every** device `adb devices` sees at startup (`backend/device/registry.py`) rather than pinning one serial — target a specific one per-request instead via `device_serial` in the Explore/Deploy request body |
| `CHROMA_HOST` / `CHROMA_PORT` | no | unset = local on-disk ChromaDB in `./kb_data`; set (Compose sets `chromadb`/`8000`) to use a remote instance |
| `PRICE_GEMINI_INPUT_PER_1M` / `PRICE_GEMINI_OUTPUT_PER_1M` (and `_OPENAI_`/`_ANTHROPIC_` equivalents) | no | override the approximate $/1M-token figures in `backend/llm/pricing.py` used for `estimated_cost_usd` — the defaults are placeholders, verify against each provider's actual pricing page before trusting cost totals |

The `provider` field is also sent per-request in the Explore/Deploy API calls
(`ExploreRequest.provider` / `DeployRequest.provider`), so `LLM_PROVIDER` in `.env` is really just
the frontend's default selection, not a hard backend lock.

### Choosing a provider

- **Gemini** (default) — good vision quality, generous free tier, recommended starting point.
- **OpenAI (gpt-4o)** / **Anthropic (claude-opus-5)** — strongest reasoning, no free tier.
- **Ollama** — fully local/private, needs a vision-capable model pulled (`qwen2.5vl` is the
  default). Slower and lower quality than cloud options on typical hardware.
- **GLM** — free tier with vision support, useful as a backup when rate-limited elsewhere.
- **Cerebras** — fast and cheap, but text-only. Only usable for the Deploy planner call; it will
  raise if used for any vision call.

## Getting an Android target running

### Option A — existing emulator or physical device
Confirm it's visible first:
```bash
adb devices
```
For a physical device, enable Developer Options → USB debugging and accept the RSA prompt. The
backend connects to **every** device `adb devices` shows at startup (`backend/device/registry.py`)
— multiple emulators/phones can run agent sessions in parallel, see `GET /device/list`.

### Option A2 — physical device over Wi-Fi (no cable needed after pairing)
Android 11+: Settings → Developer options → Wireless debugging → "Pair device with pairing code"
gives a 6-digit code and one `ip:port`. Either run the classic CLI (`adb pair ip:port code`, then
`adb connect` the *other* `ip:port` shown on the main Wireless debugging screen — the two ports
differ), or use the backend's own endpoints: `POST /device/pair {ip, port, code}` then
`POST /device/connect {ip, port}` (see [docs/API.md](API.md#post-apiv1devicepair)). Screenshots
and `uiautomator dump` are noticeably slower over Wi-Fi than USB — worth knowing if you're timing
runs.

### Option B — boot a fresh headless AVD
```bash
export AVD_NAME=MobileAgent      # optional, this is the default
export API_LEVEL=34              # optional
bash scripts/setup_emulator.sh
```
This installs the system image via `sdkmanager`, creates the AVD if it doesn't exist, boots it
headless (`-no-window -no-audio`), waits for boot completion, and dismisses the keyguard. Requires
`sdkmanager`, `avdmanager`, and `emulator` on `PATH` (part of Android SDK cmdline-tools).

## Navigation graph (optional, Neo4j)

Explore mode records screen-to-screen transitions if Neo4j is reachable — entirely optional, fails
soft if it isn't (`backend/graph/neo4j_client.py`). Bring it up via `docker compose up neo4j` (see
`docker-compose.yml`) or standalone:
```bash
docker run -d --name mobile-agent-neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/learnGraph123 neo4j:latest
```
Defaults (`bolt://localhost:7687`, `neo4j`/`learnGraph123`) match `docker-compose.yml`'s service —
override via `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD` in `.env` if you're pointing at something
else. Browse the graph at `http://localhost:7474`. Nothing reads from it yet (write-only today) —
see [docs/ARCHITECTURE.md](ARCHITECTURE.md#navigation-graph-neo4j).

## Observability (optional, Langfuse)

Unset by default — zero behavior change, zero network calls. To enable: get free-tier keys at
[cloud.langfuse.com](https://cloud.langfuse.com), set `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`
in `.env`, restart the backend. Every Explore/Deploy session becomes a trace, every LLM call a
nested generation — provider, latency, token usage, redacted prompt (screenshots are never sent,
logged as `"[+1 image, omitted]"` instead). See
[docs/ARCHITECTURE.md](ARCHITECTURE.md#langfuse-observability-optional).

## Credentials (for the `type_secret` action)

If a task needs to type a password/PIN/token, don't let the LLM guess or fabricate one:
```bash
cp secrets.example.yaml secrets.yaml    # gitignored — real values never get committed
```
Edit `secrets.yaml`:
```yaml
secrets:
  YOUTUBE_PASSWORD:
    value: "your-real-password"
    enabled: true
```
The LLM only ever sees the key name (`YOUTUBE_PASSWORD`), never the value — see
[docs/ARCHITECTURE.md](ARCHITECTURE.md#credential-vault-type_secret). `secrets.yaml` is loaded
once at backend startup; restart the backend after editing it.

## App cards (optional, speeds up known apps)

`app_cards/app_cards.json` maps an `app_name` to a markdown file in `app_cards/` with hand-written
navigation notes — no exploration needed for apps you already know. See `app_cards/youtube.md` for
the existing example. Add an entry and a `.md` file, restart the backend, done — see
[docs/ARCHITECTURE.md](ARCHITECTURE.md#app-cards).

## Running locally (no Docker)

```bash
# 1. backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```
Watch the startup log — it prints the connected device serial and resolution, or a warning if no
device was found (the API still starts; device-dependent endpoints return `503` until one connects).

```bash
# 2. frontend, separate terminal
cd frontend
npm install
npm run dev
```
Vite serves on `http://localhost:5173` and proxies `/api` and `/ws` to `localhost:8000`
(`vite.config.ts`) — no extra config needed.

ChromaDB runs embedded/local by default (`./kb_data` directory, created automatically), so no
separate service is required for local dev unless you explicitly set `CHROMA_HOST`.

## Running with Docker Compose

```bash
docker compose up --build
```
This starts three services (`docker-compose.yml`):
- `chromadb` — port 8001→8000, persists to `./kb_data`
- `backend` — port 8000, runs `privileged: true` with `/dev/bus/usb` mounted so ADB can reach a
  USB-attached physical device from inside the container (an emulator on the host is reached over
  the network instead — set `ANDROID_SERIAL` and ensure `adb` on the host is listening in a way
  the container can reach, e.g. `adb -a` or host networking, depending on your platform)
- `frontend` — port 80, built and served via nginx (`frontend/nginx.conf` proxies `/api/` and
  `/ws/` to `backend:8000`)

Set your API keys either in `.env` (picked up via `${VAR}` interpolation in `docker-compose.yml`)
or export them in your shell before running `docker compose up`.

## Tests

```bash
cd backend
pip install pytest
pytest tests/ -v
```
Current coverage is perception-only: `test_xml_parser.py` (uiautomator XML → element parsing,
sorting, ID assignment, bounds filtering) and `test_annotator.py` (screenshot annotation produces
valid, correctly-sized PNGs). There are no tests yet for the agent loop, LLM client, KB store, or
API routers — see [CONTRIBUTING.md](../CONTRIBUTING.md) if you're adding one of those.

Frontend has no test setup at all (`package.json` has no `test` script).

## Benchmarking Deploy mode

```bash
cd scripts
python run_benchmark.py --app linkedin --tasks tasks/linkedin.json --provider gemini
```
Tasks file format:
```json
[
  { "task": "Find a software engineering job in Bangalore", "optimal_rounds": 6 },
  { "task": "Search for Python developer roles", "optimal_rounds": 4 }
]
```
The backend must already be running (`--base-url` defaults to `http://localhost:8000`) and have a
device connected. Reports three metrics: **Task Success Rate** (fraction completed),
**Cost Efficiency** (mean `actual_rounds / optimal_rounds`, lower is better), and
**KB Utilisation Rate** (whether the app's KB was pre-populated before the run started).

## Common issues

- **Emulator crashes on boot with a "bad color buffer handle" / GPU error** — happened during
  development when running Ollama (VRAM-heavy vision model) and the emulator's hardware-accelerated
  rendering (`-gpu host`, the default) on the same GPU at once, on an 8GB-class card. Under
  contention Windows can trigger a driver TDR (Timeout Detection and Recovery) reset, which
  invalidates the emulator's GPU context mid-render. Fix: launch with `-gpu swiftshader_indirect`
  (software rendering — slower, but avoids the VRAM fight entirely), or don't run local Ollama
  vision inference and the emulator simultaneously on a memory-constrained GPU.
- **`503 No idle Android device available`** — `adb devices` must show at least one target as
  `device` (not `unauthorized` or `offline`) before starting the backend, or before calling any
  device/agent endpoint. The registry connects to everything visible once at FastAPI startup
  (`api/main.py`'s `lifespan`); it does not currently retry or reconnect automatically if a device
  drops mid-session — restart the backend after reconnecting. If you passed an explicit
  `device_serial`, the 503 detail will instead say `Device '<serial>' not found or busy` — check
  `GET /device/list` to see what's actually connected and whether it's already in use by another
  session.
- **`429 Too Many Requests` from Gemini** — the free tier's per-minute quota is low and shared
  across every round of every session; back-to-back test runs exhaust it fast (`_gemini_request`
  in `llm/vision.py` retries with 5s/15s/30s backoff, but that doesn't help if the quota is
  genuinely exhausted for the window, not just rate-limited for a moment). Switch to `ollama` for
  local/free testing, or set a `max_llm_calls`/`max_cost_usd` limit (see
  [docs/API.md](API.md#post-apiv1agentexplore)) so a run fails fast and cleanly instead of burning
  through every remaining round on 429s.
- **Typed text comes out garbled or truncated on some fields** — `device.text()` chunks input and
  adds small delays between chunks specifically to work around `adb shell input text` dropping
  characters on longer strings (`backend/device/controller.py`). If it's still wrong on a
  *specific* field, that's more likely the field itself re-rendering mid-type (e.g. a live-search
  suggestion box redrawing) than the injection method — confirmed by testing the exact same string
  against a plain `EditText` with no live suggestions, which came through perfectly.
- **Agent completes a task with the wrong content** (e.g. searches for something other than what
  was asked) — check whether the target app had pre-existing state (recent search history,
  autofill, a previous test's leftover query) that the model may have latched onto instead of
  typing fresh input. `DEPLOY_SYSTEM` and `build_progress_prompt` in `llm/prompts.py` were
  hardened against exactly this after it happened during real testing, but it's a real failure
  mode worth watching for, not fully eliminated.
- **LLM call raises "invalid JSON"** — some providers (notably the OpenAI-compatible ones without
  native JSON mode) occasionally wrap the response in prose or markdown fences despite the
  prompt's instruction. `_parse_json()` in `backend/llm/vision.py` strips one level of code
  fences; anything beyond that will surface as a round-level error appended to `state.errors`
  rather than crashing the run.
- **Ollama vision runs very slowly / GPU shows high CPU%** — a vision-capable model (e.g.
  `qwen2.5vl`) plus a large context window (`OLLAMA_NUM_CTX` in `llm/vision.py`, default 8192) can
  exceed available VRAM on 8GB-class GPUs, spilling most of the model to CPU (`ollama ps` shows
  the CPU/GPU split). Lower `OLLAMA_NUM_CTX`, use a smaller model, or accept it'll be slow.
- **Cerebras vision error** — expected; Cerebras has no vision model. Use it only as a text
  provider or pick a different provider for Explore/Deploy.

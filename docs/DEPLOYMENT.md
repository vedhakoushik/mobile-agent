# Deploying to AWS

Requirements, blockers, and pending work for hosting mobile-agent on AWS.

Read section 1 first — it decides the whole architecture.

---

## 1. The blocker: AWS has no phones

This project's core loop drives a **physical Android device over ADB**. The
current `docker-compose.yml` makes that explicit:

```yaml
backend:
  volumes:
    - /dev/bus/usb:/dev/bus/usb   # USB passthrough to the phone
  privileged: true
```

There is no AWS equivalent of "plug a phone into this container". Fargate
won't run `privileged` containers at all. So a straight lift-and-shift of
compose onto ECS **cannot work** — the backend would start, serve the UI, and
fail every single agent run with "No Android device connected".

Pick one of these before writing any infrastructure code.

### Option A — Hybrid: AWS control plane, devices stay local *(recommended)*

Split the backend in two:

- **Cloud (AWS):** API, web UI, chat/intent inference, session persistence,
  KB, navigation graph, observability.
- **Local device agent:** a small long-lived process on a machine with the
  phones physically attached. It holds an outbound WebSocket to the cloud,
  receives actions (`tap`, `text`, `swipe`, `screenshot`, `pull_xml`), runs
  them through ADB, and streams results back.

**Why this one:** it's the only option that keeps real hardware in the loop
without paying for emulator instances, and outbound-only connections mean no
inbound firewall/NAT work on the device host — which is exactly the class of
problem that broke the phone→laptop connection during local testing (campus
Wi-Fi client isolation, Windows Firewall on a Public profile).

**Cost:** the largest chunk of work here. `DeviceController` currently talks
to `adbutils` directly; it would need to become an interface with two
implementations (local ADB, remote-over-WebSocket). The agent loop itself
wouldn't change — it already only calls `screenshot / pull_xml / tap / text /
swipe / long_press / key_event / launch_app / wait_idle`, which is a small,
clean surface to proxy.

### Option B — Android emulators on EC2

Run emulators in the cloud, no physical devices.

- Needs **nested virtualisation** → bare-metal instances (`c5.metal`,
  `m5.metal`) or `mac` instances. Not `t3.micro`.
- Roughly **$0.50–$4/hour** depending on instance — verify against current
  pricing, this is the dominant cost line.
- Emulators are also genuinely different from real devices: no real Play
  Store apps in many cases, different performance envelope, and app anti-
  emulator checks can trip.

Good for CI and benchmark runs (`backend/eval/run_benchmark.py`), weaker as
the product path.

### Option C — AWS Device Farm

Real devices, AWS-managed. But it's built around **test-suite runs**, not a
long-lived interactive ADB session. Direct ADB access is limited. Likely a
poor fit for an interactive agent; worth a spike before committing.

---

## 2. Pending work before any AWS deploy

Things that are fine on a laptop and break in the cloud. Each is real and
currently unaddressed.

### 2.1 Blockers

| # | Issue | Where | Fix |
|---|---|---|---|
| 1 | Device access (section 1) | `docker-compose.yml`, `backend/device/` | Pick option A/B/C |
| 2 | **API key is shipped to the browser** | `frontend/src/api/client.ts` | See 2.2 — do not deploy publicly as-is |
| 3 | SQLite on local disk | `backend/persistence/db.py` (`_DB_PATH`) | Move to RDS Postgres |
| 4 | Sessions live in a process-local dict | `routers/agent.py` `_sessions` | Single instance only, or move to Redis/DynamoDB |
| 5 | ChromaDB `PersistentClient` on local disk | `knowledge_base/store.py` | Run Chroma as a service (`CHROMA_HOST` is already supported) or mount EFS |
| 6 | Hardcoded Neo4j password | `docker-compose.yml`, `graph/neo4j_client.py` default | Secrets Manager; remove the `learnGraph123` default |
| 7 | No TLS | everywhere | ALB + ACM certificate |
| 8 | CORS pinned to localhost | `api/main.py` | Drive `allow_origins` from env |

### 2.2 The API key problem — read before going public

`frontend/src/api/client.ts` embeds `VITE_API_KEY` at build time, with this
comment:

> acceptable for this project's single-user local-dev model (the person
> running the frontend build is the same person running the backend on their
> own machine), not a substitute for real auth in a multi-user deployment.

That assumption dies the moment this is on the public internet. Vite inlines
the value into the JS bundle, so **anyone who loads the page can read the key
and drive your phone**. The Android app has the same shape (key in
`SharedPreferences`), but that's a per-device install the user configures
themselves, not a public download — different risk.

Before any internet-facing deploy, replace the shared static key with real
per-user auth: Cognito (or any OIDC provider) issuing short-lived tokens, and
`ApiKeyAuthMiddleware` swapped for JWT verification. The middleware is small
and already centralised (`backend/security/auth.py`), so the change is
contained — but it is not optional.

### 2.3 Also worth fixing

- **`android/app/src/main/res/xml/network_security_config.xml`** currently
  sets `cleartextTrafficPermitted=true` app-wide. Once the backend is behind
  HTTPS, drop it back to TLS-only.
- **WebSocket + horizontal scaling.** `ws/manager.py` keeps connections in
  process memory. More than one backend task requires either sticky sessions
  on the ALB or a shared pub/sub (Redis/MQTT).
- **`privileged: true`** must go. It's container-escape territory and blocks
  Fargate entirely.
- **Secrets.** `.env` and `secrets.yaml` are gitignored (good) but need to
  become Secrets Manager / SSM Parameter Store entries injected as env vars.

---

## 3. Target architecture (Option A)

```
                    Route 53  →  ACM (TLS)
                             │
                      Application Load Balancer
                       │                    │
              ┌────────┘                    └────────┐
        ECS Fargate                            ECS Fargate
        frontend (nginx)                       backend (FastAPI)
                                                    │
                        ┌───────────────┬───────────┼──────────────┐
                        │               │           │              │
                    RDS Postgres   Chroma on     Neo4j Aura    Secrets Manager
                    (sessions,     ECS + EFS     (nav graph)   (API + LLM keys)
                     events)        (KB)
                                                    │
                                           outbound WebSocket
                                                    │
                                        ┌───────────┴───────────┐
                                        │  Local device agent   │
                                        │  (your machine)       │
                                        │  ADB → physical phone │
                                        └───────────────────────┘
```

**Service choices and why:**

| Need | Service | Note |
|---|---|---|
| Containers | ECS Fargate | No servers to patch. Requires dropping `privileged`. |
| Images | ECR | `backend/Dockerfile` and `frontend/Dockerfile` already exist |
| Sessions + events | RDS Postgres | Replaces SQLite. Schema in `persistence/db.py` is simple — two tables, portable. |
| KB vectors | Chroma on ECS + EFS | `CHROMA_HOST`/`CHROMA_PORT` env vars already supported |
| Nav graph | Neo4j Aura | Managed; avoids running Neo4j yourself. Free tier exists. |
| Secrets | Secrets Manager | Injected as ECS task env vars |
| Logs/metrics | CloudWatch | Backend already uses `logging` throughout |
| LLM traces | Langfuse Cloud | Already integrated and verified working |

---

## 4. Rough cost

Order-of-magnitude only. **Verify against current AWS pricing** — these are
estimates, not quotes.

| Item | Est. $/month |
|---|---|
| ECS Fargate (backend, 0.5 vCPU / 1 GB, always on) | ~$15–20 |
| ECS Fargate (frontend, 0.25 vCPU / 0.5 GB) | ~$8–10 |
| RDS Postgres `db.t4g.micro` | ~$12–15 |
| ALB | ~$16 + traffic |
| Chroma on ECS + EFS | ~$10–15 |
| Neo4j Aura | free tier, or ~$65 paid |
| Secrets Manager | ~$0.40/secret |
| **Total (Aura free tier)** | **~$65–80/month** |

Plus LLM API spend, which is usage-driven and tracked per session already
(`estimated_cost_usd`). Note the audit fix: planner/reflector/grid calls are
now counted, so those numbers are accurate — they previously understated real
spend.

Option B (emulators on metal) adds **$350–$3000/month** for an always-on
instance and dominates everything else. Run it on-demand, not 24/7.

---

## 5. Suggested order

1. **Decide section 1.** Nothing else can be designed until the device story
   is settled.
2. **Replace the shared API key with real auth** (2.2). Everything after this
   is safe to expose; before it, nothing is.
3. **SQLite → Postgres.** Self-contained: `persistence/db.py` is the only
   module that touches it, and its tests (`tests/test_persistence.py`)
   already run against a temp DB, so they'll port.
4. **Externalise config** — CORS origins, Neo4j credentials, `CHROMA_HOST`.
   Remove hardcoded defaults.
5. **Containerise properly.** Drop `privileged`, drop the USB mount, push to
   ECR. CI (`.github/workflows/ci.yml`) already builds and tests both
   services — extend it to build/push images.
6. **Stand up infrastructure.** Terraform or CDK; avoid console click-ops so
   it's reproducible.
7. **Device agent** (if Option A) — the largest single piece of new code.
8. **Then scale:** move `_sessions` out of process memory and add WebSocket
   pub/sub, only once more than one backend task is actually needed.

---

## 6. What's already deploy-ready

Worth noting, so it doesn't get rebuilt:

- **Dockerfiles** exist for both backend and frontend.
- **CI** runs lint + 89 tests on every push, currently green.
- **Auth middleware** is centralised and covers REST + WebSocket, with
  timing-safe comparison — the *mechanism* is sound, it's the shared-static-
  key *model* that needs replacing.
- **Config is env-var driven** already (`.env.example` documents the full
  surface), which maps cleanly onto ECS task definitions.
- **Health endpoints**: `/api/v1/health` (liveness, auth-exempt — suitable as
  an ALB health check) and `/api/v1/device/health/detailed` (dependency
  status).
- **Fail-soft integrations**: Neo4j, Langfuse and persistence all degrade
  gracefully when unreachable, so partial infrastructure outages don't take
  the agent down.
- **Observability**: Langfuse tracing is wired and verified end-to-end.

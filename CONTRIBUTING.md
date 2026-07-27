# Contributing

This is a young, single-maintainer project — process is intentionally light. The main goal of
this doc is to make it easy to add a change without having to reverse-engineer conventions from
scratch.

## Before you start

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first if your change touches the agent loop,
LLM layer, or knowledge base — several design choices there (in-memory session state, heuristic
sub-step advancement, one shared ChromaDB collection) are documented trade-offs, not oversights.
If you want to revisit one of them, say so in the PR description rather than silently changing
behavior.

## Local setup

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for environment variables, running the backend and
frontend, and running tests.

## Code style

**Backend (Python)**
- Type hints on function signatures (the codebase already does this consistently — match it).
- `async def` for anything that calls the device, an LLM provider, or ChromaDB — the agent loop is
  entirely async and blocking calls will stall every session.
- Keep provider-specific LLM code isolated to `backend/llm/vision.py` — the agent loop should only
  ever call `call_vision_llm` / `call_dual_vision_llm` / `call_text_llm`, never a provider SDK
  directly.
- No formatter/linter is currently configured for the backend — match the existing style
  (double-quoted strings, trailing section comment banners like `# ── Foo ──`) rather than
  introducing a new one unannounced.

**Frontend (TypeScript/React)**
- `npm run lint` before opening a PR (ESLint config already present).
- Components are function components with hooks; shared state goes through the Zustand store
  (`frontend/src/store/agentStore.ts`), not prop drilling or context.
- Tailwind utility classes only — no new CSS files.

## Tests

- New backend logic that's pure/deterministic (parsing, formatting, scoring heuristics) should
  get a pytest unit test under `backend/tests/`, following the style of `test_xml_parser.py` and
  `test_annotator.py` (plain function tests, no fixtures framework beyond what's already there).
- Logic that depends on a live device or a real LLM call is hard to unit test today — if you're
  adding a feature there, at minimum keep the device/LLM interaction isolated behind a function
  that can be mocked, the way `execute_action` and `call_vision_llm` already are.
- Run `pytest backend/tests/ -v` before opening a PR; there's no CI configured yet to catch this
  automatically.

## Adding an LLM provider

Concrete example of the shape a substantial contribution takes here:

1. Add `_<name>_vision`, `_<name>_dual_vision`, `_<name>_text` functions in `backend/llm/vision.py`
   following the existing providers' pattern (each returns a `dict` via `_parse_json()`).
2. Add the dispatch branch for `<name>` in `call_vision_llm`, `call_dual_vision_llm`, and
   `call_text_llm`.
3. Add `<name>` to the `Literal[...]` provider type in `backend/api/schemas.py` for both
   `ExploreRequest` and `DeployRequest` — otherwise the API will reject it with a 422.
4. Add the provider to the `<select>` options in `frontend/src/pages/ExplorePage.tsx` and
   `DeployPage.tsx` so it's selectable from the UI.
5. Note in your PR description whether the provider supports vision at all, and whether it
   supports true dual-image input or needs the single-image fallback (see
   [ARCHITECTURE.md](docs/ARCHITECTURE.md#multi-provider-llm-layer) for why that distinction
   matters for reflection quality).
6. Add the new env vars to `.env.example` with a one-line comment, matching the existing entries.

## Security note for reviewers

There is currently no authentication on the API or WebSocket, and the FastAPI CORS policy allows
all origins in dev (`api/main.py`). Do not merge changes that assume this is safe to expose beyond
localhost/a trusted network without first adding auth — flag it in review if a PR moves in that
direction.

## Commit / PR conventions

- Keep commits scoped to one logical change; the loop, executor, and prompts are tightly coupled,
  so a PR touching one should explain in its description how it was tested against the others.
- Update the relevant doc (`README.md`, `docs/ARCHITECTURE.md`, `docs/API.md`,
  `docs/DEVELOPMENT.md`) in the same PR as the code change it describes — a stale doc is worse
  than no doc.

# How this compares to existing mobile agents

This is an honest assessment, not a sales pitch. It's based on real published benchmark numbers,
not this project's own claims — **this project has no formal evaluation of its own** (no benchmark
harness beyond `scripts/run_benchmark.py`'s small internal TSR/CE/KUR metrics, no AndroidWorld or
similar submission). Where this doc says "we're weaker," take that at face value.

## The real numbers

A third-party benchmark tested four open-source mobile agents across 65 real-world Android tasks
([aimultiple.com/mobile-ai-agent](https://aimultiple.com/mobile-ai-agent)):

| Agent | Success rate | Cost/success | Avg time | Architecture |
|---|---|---|---|---|
| DroidRun | 43% | $0.075 | — | Accessibility-tree-first + explicit multi-step planning |
| Mobile-Agent | 29% | $0.025 | — | Vision-based, lighter reasoning |
| AutoDroid | 14% | $0.017 | 57s | XML parsing, minimal reasoning |
| AppAgent | 7% | $0.90 | 180s | Pure vision, every round |

Separately, current SOTA research agents (fine-tuned grounding models, hierarchical reflection,
program-guided context management) score 62–90%+ on the AndroidWorld benchmark — but that
benchmark is now considered saturated by researchers, meaning even that ceiling is contested as too
easy. See [AgentProg](https://arxiv.org/pdf/2512.10371), [K²-Agent](https://arxiv.org/pdf/2603.00676).

## Where this project actually sits

**Structurally closest to AppAgent — the worst performer in that table.** This agent calls a
vision LLM with a full screenshot on every single round (`backend/agent/loop.py`), with no
accessibility-tree-primary reasoning path. That's the exact architectural choice the benchmark
measured as 7% success / $0.90 per success / 180s average — not a coincidence, the same design
decision.

We have zero measured success rate of our own. What we do have from actual testing during
development: one real correctness failure (agent searched the wrong query after latching onto a
stale UI suggestion — see `backend/llm/prompts.py`'s `build_progress_prompt` for the mitigation
added), and repeated free-tier rate-limit exhaustion on multi-round runs. Nothing about that
suggests we'd beat the 7–29% range today.

## Where we match or exceed DroidRun's published feature set

- **`type_secret` credential vault** (`backend/security/credentials.py`) — LLM only ever sees a
  secret's name, never its value; resolution happens server-side in `agent/executor.py`. This
  matches DroidRun's own `type_secret` design (verified by reading their actual source, not just
  their docs).
- **App cards** (`backend/app_cards/`) — static per-app guidance injected into prompts, same
  concept as DroidRun's `app_cards/` feature. Where we differ: DroidRun keys by real Android
  package name (auto-detected); we key by the user-supplied `app_name` string, matching this
  project's existing convention everywhere else (KB, credentials).
- **Multi-device registry** (`backend/device/registry.py`) — not confirmed in DroidRun's public
  source at the time this was checked.

## Where we're behind, concretely

1. **No accessibility-tree-primary reasoning.** The single biggest lever, per the benchmark table
   above. `backend/perception/xml_parser.py` already parses the full UI tree every round — it's
   just not used as the *primary* signal, only as context alongside the screenshot. Fixing this is
   the highest-priority architectural change on the roadmap.
2. **No fine-tuned grounding model.** SOTA systems use models trained specifically for GUI
   element grounding; this project uses general-purpose vision LLMs (Gemini/GPT-4o/Claude/etc.)
   asked to reason about a screenshot from scratch every time.
3. **No navigation-path memory.** The knowledge base is semantic/vector-only (ChromaDB) — it
   stores "what does this element do" but not "what sequence of screens gets me from A to B." A
   graph-DB-backed navigation model is on the roadmap for this reason.
4. **No benchmark harness against a standard suite.** We can't honestly claim a number without
   running one.

## Scalability, honestly

Single-process FastAPI, module-level singletons for credentials/app-cards, one ChromaDB instance,
in-memory session dict, no auth, no multi-tenancy, a plaintext local `secrets.yaml`. Fine for one
person on one laptop. Multi-device support (`backend/device/registry.py`) is the first real step
away from "single-everything" — auth, per-user isolation, and horizontal scaling are all still
open problems, not yet addressed.

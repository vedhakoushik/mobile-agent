# Performance analysis

A pass over the hot paths — the per-round agent loop, the device layer, and
the data stores — looking for wasted latency and blocked concurrency.

Numbers below that are marked **measured** came from running the code.
Anything marked *estimated* is arithmetic from constants in the source
(e.g. explicit `asyncio.sleep` calls), not a benchmark.

---

## 1. Implemented

### 1.1 Concurrent device capture — saves one ADB round-trip per round

`run_explore` and `run_deploy` both opened each round with:

```python
raw_png = await state.device.screenshot()   # ADB round-trip
raw_xml  = await state.device.pull_xml()    # ADB round-trip
```

These are independent — neither uses the other's result — but ran
sequentially. Now:

```python
raw_png, raw_xml = await asyncio.gather(
    state.device.screenshot(), state.device.pull_xml()
)
```

Round-trip cost is dominated by the device, not the host, so this cuts
capture time to roughly the slower of the two instead of their sum. Applies
to every round of every run.

> Not benchmarked end-to-end: the test phone was disconnected when this pass
> ran. The structural claim (two independent I/O waits overlapped rather than
> serialized) holds regardless, but the exact millisecond saving is unverified.

### 1.2 Event-loop blocking — the bigger problem

This server runs many agent sessions concurrently (fan-out, plus the
WebSocket feed). Any synchronous call inside `async def` freezes *all* of
them, not just the caller.

Three offenders, all now moved to `asyncio.to_thread`:

| Call | Cost | Frequency |
|---|---|---|
| `annotate_screenshot()` | **measured 59 ms** (10 elements) → **99 ms** (60 elements) | every round |
| `nav_graph.record_transition()` | one Neo4j round-trip (sync bolt driver) | every Deploy round |
| `nav_graph.get_outgoing_transitions()` | one Neo4j round-trip | every Deploy round |

`neo4j.GraphDatabase.driver` is the *synchronous* client. Every call held the
event loop for the full network round-trip.

### 1.3 Blocking ChromaDB reads in the KB router

`routers/kb.py` called `kb.get_all()` / `kb.clear()` — synchronous ChromaDB —
directly inside `async def` endpoints. The `KnowledgeBase` constructor is also
blocking (it opens a `PersistentClient`, i.e. disk I/O) and ran on *every*
request. All offloaded.

Note the hot agent path (`store.upsert`, `store.retrieve_context`) was already
correct — it used `to_thread` internally. Only the router-side reads were
blocking.

---

## 2. Analyzed and deliberately left alone

Checked, found not worth changing — recorded so this ground isn't re-covered.

| Area | Finding |
|---|---|
| `parse_interactive_elements()` | **measured 0.1–0.4 ms** for 10–60 elements. Not a bottleneck. |
| `screen_signature()` | `sorted()` over elements, O(n log n) with n ≈ tens. Negligible, and sorting is required for the hash to be order-stable. |
| `executor._find_element()` | Linear scan per action, but n is small and it runs once per round. A dict index would add bookkeeping for no measurable gain. |
| `_history_txt` / `build_deploy_prompt` | Already caps history at first + last 5 entries, so prompt size doesn't grow with round count. Correct as-is. |
| KB search substring filter | Client-side scan over `get_all()`. ChromaDB's `where` can't express substring match. Fine at per-app KB sizes; revisit if one app's KB grows large. |

---

## 3. Recommended, not implemented

These need a judgement call or carry behavioural risk, so they're listed
rather than applied.

### 3.1 Fixed sleeps in the device layer — the largest remaining cost

`backend/device/controller.py` pads every action with a constant sleep:

| Action | Sleep | Notes |
|---|---|---|
| `launch_app()` | 2.00 s | once per run |
| `long_press()` | 1.20 s | per action |
| `tap()` | 0.80 s | **per action — every round** |
| `swipe()` | 0.40 s | per action |
| `key_event()` | 0.30 s | per action |
| `text()` | 0.12 s per 4 chars + 0.30 s | *estimated* ~1.5 s for a 40-char string |

These are worst-case guesses at "how long until the UI settles". `tap()` at
0.8 s is the expensive one because it fires nearly every round.

**Better approach:** poll for actual UI settling instead of sleeping a fixed
amount — capture the XML hierarchy, and proceed as soon as two consecutive
reads match (or a ceiling is hit). Typical case would drop well under 0.8 s
while slow screens get *more* time than they do now, so it should be more
reliable as well as faster.

**Why not done here:** timing changes in the action layer risk introducing
flaky, hard-to-reproduce failures where the agent acts on a half-rendered
screen. Wants a real device and a repeatable benchmark to validate — which
wasn't available during this pass.

### 3.2 `text()` chunking

Types 4 characters at a time with a 0.12 s pause between chunks. The comment
explains why (`adb shell input text` drops characters on long strings), which
is a real problem — but 4 chars is conservative. Worth testing 8–16 on a real
device; would roughly halve typing latency.

### 3.3 `wait_idle()` runs a full `uiautomator dump`

```python
async def wait_idle(self) -> None:
    await asyncio.to_thread(self._device.shell, "uiautomator dump /dev/null")
```

Called after every action in both loops. `uiautomator dump` is one of the more
expensive ADB operations, and here its output is thrown away — it's used
purely as a "block until the UI is quiet" barrier. Since the very next thing
the loop does is `pull_xml()` (another dump), this is close to duplicated
work. Folding the two together would remove one expensive call per round.

### 3.4 ChromaDB client is reconstructed per request

`KnowledgeBase(app_name=...)` opens a new `PersistentClient` on every KB
request and on every agent session. Caching one client per app name (module
level, like `_credentials` / `_nav_graph` in the agent router) would remove
repeated disk-open work. Low risk, but touches shared state — worth doing
deliberately rather than as a drive-by.

### 3.5 Screenshots are sent to the frontend as base64 over WebSocket

Every round broadcasts a full-resolution annotated PNG as base64 (~33 % size
overhead on an already-large payload). Options: downscale before broadcast,
encode as JPEG/WebP for the *preview* only (keeping full PNG for the LLM), or
push a URL instead of inline bytes. Meaningful bandwidth win on slow links,
no effect on agent accuracy.

---

## 4. Where the round time actually goes

Rough shape of one Deploy round, to keep optimization effort proportionate:

```
LLM call            ~1–5 s      dominant, provider-bound
tap + wait_idle     ~0.8 s + uiautomator dump
screenshot+pull_xml   now concurrent (was sequential)
annotate            ~60–100 ms  now off the event loop
Neo4j ×2            network     now off the event loop
parse XML           ~0.3 ms     negligible
```

**The LLM call dominates.** The biggest available win is not micro-optimizing
Python — it's cutting round count or LLM calls per round:

- `reasoning_mode="fast"` (now the default) already does this: a text-only
  call, escalating to vision only when the model can't identify an element
  confidently.
- The Neo4j navigation graph feeds known transitions into the prompt, which
  should reduce wasted exploratory rounds. Its real effect is not yet
  measured — worth doing, since it justifies the Neo4j dependency.
- The usage limiter now counts planner/reflector/grid calls that were
  previously invisible (see the audit commit), so cost ceilings are enforced
  accurately.

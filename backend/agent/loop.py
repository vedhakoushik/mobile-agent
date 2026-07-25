import asyncio
import base64

from ..perception import parse_interactive_elements, annotate_screenshot
from ..llm import call_vision_llm, call_text_llm
from ..llm.prompts import build_explore_prompt, build_deploy_prompt, build_progress_prompt
from .state import AgentState
from .planner import run_planner
from .executor import execute_action
from .reflector import run_reflector


async def run_explore(state: AgentState) -> None:
    """Explore phase: systematically interact with all UI elements and build KB."""
    state.status = "running"
    await state.broadcast({"type": "status_change", "status": "running", "mode": "explore"})

    try:
        while state.round_num < state.max_rounds and not state.task_complete:
            if state.status == "paused":
                await asyncio.sleep(0.5)
                continue

            # ── 1. Capture ────────────────────────────────────────────────────
            raw_png = await state.device.screenshot()
            raw_xml = await state.device.pull_xml()

            # ── 2. Parse elements ─────────────────────────────────────────────
            elements = parse_interactive_elements(raw_xml)
            state.elements = [e.to_dict() for e in elements]

            # ── 3. Annotate screenshot ────────────────────────────────────────
            annotated_b64 = annotate_screenshot(raw_png, elements)
            state.screenshot_b64 = annotated_b64
            state.raw_screenshot = raw_png

            # ── 4. Broadcast screenshot update to frontend ────────────────────
            await state.broadcast({
                "type": "screenshot_update",
                "screenshot": annotated_b64,
                "round": state.round_num,
                "element_count": len(elements),
            })

            # ── 5. Retrieve KB context ────────────────────────────────────────
            docs_context = await state.kb.retrieve_context(elements)

            # ── 6. LLM decision ───────────────────────────────────────────────
            prompt = build_explore_prompt(state, state.elements, docs_context)
            try:
                decision = await call_vision_llm(state.provider, annotated_b64, prompt)
            except Exception as e:
                state.errors.append(f"Round {state.round_num} LLM error: {e}")
                state.round_num += 1
                continue

            # attach provider for grid mode sub-calls
            decision["_provider"] = state.provider

            # ── 7. Broadcast action event ─────────────────────────────────────
            await state.broadcast({
                "type": "action_event",
                "round": state.round_num,
                "action": decision.get("action", ""),
                "element_id": decision.get("element_id"),
                "thought": decision.get("thought", ""),
                "observation": decision.get("observation", ""),
            })

            # ── 8. Check for finish ───────────────────────────────────────────
            if decision.get("action") == "finish":
                state.task_complete = True
                break

            # ── 9. Execute action ─────────────────────────────────────────────
            await execute_action(state.device, decision, state.elements)

            # ── 10. Wait for UI to settle ─────────────────────────────────────
            await state.device.wait_idle()

            # ── 11. Reflect — generate KB doc for novel elements ──────────────
            is_novel = decision.get("is_novel_element", True)
            elem_id = decision.get("element_id")
            elem_sig = _get_elem_sig(state.elements, elem_id)

            if is_novel and elem_id is not None and elem_sig not in state.explored_elements:
                after_png = await state.device.screenshot()
                doc = await run_reflector(state, raw_png, after_png, decision, state.elements)
                if doc:
                    await state.kb.upsert(doc)
                    state.explored_elements.add(elem_sig)
                    await state.broadcast({"type": "kb_update", "doc": {
                        "id": doc.id,
                        "documentation": doc.documentation,
                        "element_sig": doc.element_sig,
                        "app_name": doc.app_name,
                    }})

            # ── 12. Record history ────────────────────────────────────────────
            state.action_history.append({
                "round": state.round_num,
                "action": decision,
                "element_sig": elem_sig,
            })
            state.round_num += 1

    except Exception as e:
        state.status = "error"
        state.errors.append(str(e))
        await state.broadcast({"type": "error", "message": str(e)})
        return

    state.status = "done"
    await state.broadcast({
        "type": "status_change",
        "status": "done",
        "task_complete": state.task_complete,
        "kb_count": state.kb.count(),
    })


async def run_deploy(state: AgentState) -> None:
    """Deploy phase: complete a user-specified task using the KB."""
    state.status = "running"
    await state.broadcast({"type": "status_change", "status": "running", "mode": "deploy"})

    # ── Planner: decompose task into sub-steps ────────────────────────────────
    state.sub_steps = await run_planner(state)
    await state.broadcast({"type": "plan_ready", "steps": state.sub_steps})

    try:
        while state.round_num < state.max_rounds and not state.task_complete:
            if state.status == "paused":
                await asyncio.sleep(0.5)
                continue

            # ── 1–3: Same as explore ──────────────────────────────────────────
            raw_png = await state.device.screenshot()
            raw_xml = await state.device.pull_xml()
            elements = parse_interactive_elements(raw_xml)
            state.elements = [e.to_dict() for e in elements]
            annotated_b64 = annotate_screenshot(raw_png, elements)
            state.screenshot_b64 = annotated_b64

            await state.broadcast({
                "type": "screenshot_update",
                "screenshot": annotated_b64,
                "round": state.round_num,
                "element_count": len(elements),
            })

            docs_context = await state.kb.retrieve_context(elements)

            # ── 4. Deploy LLM decision ────────────────────────────────────────
            prompt = build_deploy_prompt(state, state.elements, docs_context)
            try:
                decision = await call_vision_llm(state.provider, annotated_b64, prompt)
            except Exception as e:
                state.errors.append(f"Round {state.round_num} LLM error: {e}")
                state.round_num += 1
                continue

            decision["_provider"] = state.provider

            await state.broadcast({
                "type": "action_event",
                "round": state.round_num,
                "action": decision.get("action", ""),
                "element_id": decision.get("element_id"),
                "thought": decision.get("thought", ""),
                "observation": decision.get("observation", ""),
            })

            # ── 5. Check for finish or impossible ────────────────────────────
            if decision.get("action") == "finish":
                state.task_complete = True
                break

            thought = decision.get("thought", "").lower()
            if any(w in thought for w in ["cannot", "impossible", "not possible", "unable"]):
                state.failure_reason = decision.get("thought", "Task marked impossible by agent")

            # ── 6–7: Execute + wait ───────────────────────────────────────────
            await execute_action(state.device, decision, state.elements)
            await state.device.wait_idle()

            # ── 8. Advance sub-step index if current step likely complete ─────
            state.current_step_idx = min(
                state.current_step_idx + _should_advance(decision),
                len(state.sub_steps) - 1,
            )

            # ── 9. Progress check every 5 rounds ─────────────────────────────
            if state.round_num > 0 and state.round_num % 5 == 0:
                progress_png = await state.device.screenshot()
                progress_b64 = base64.b64encode(progress_png).decode()
                try:
                    prog = await call_vision_llm(
                        state.provider,
                        progress_b64,
                        build_progress_prompt(state.task),
                    )
                    if prog.get("complete"):
                        state.task_complete = True
                        await state.broadcast({
                            "type": "action_event",
                            "round": state.round_num,
                            "action": "finish",
                            "element_id": None,
                            "thought": f"Progress check: {prog.get('progress', 'task complete')}",
                            "observation": "",
                        })
                        break
                except Exception:
                    pass

            state.action_history.append({
                "round": state.round_num,
                "action": decision,
                "element_sig": _get_elem_sig(state.elements, decision.get("element_id")),
            })
            state.round_num += 1

    except Exception as e:
        state.status = "error"
        state.errors.append(str(e))
        await state.broadcast({"type": "error", "message": str(e)})
        return

    state.status = "done"
    await state.broadcast({
        "type": "status_change",
        "status": "done",
        "task_complete": state.task_complete,
        "failure_reason": state.failure_reason,
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_elem_sig(elements: list[dict], elem_id: int | None) -> str:
    if elem_id is None:
        return "unknown"
    for e in elements:
        if e["id"] == elem_id:
            return f"{e.get('resource_id','')}::{e.get('class_name','')}"
    return "unknown"


def _should_advance(decision: dict) -> int:
    """Heuristic: advance sub-step index when agent taps a submit/confirm/search button."""
    text = (decision.get("thought", "") + decision.get("observation", "")).lower()
    advance_signals = ["submitted", "searching", "navigated", "opened", "clicked submit",
                       "applied", "saved", "completed", "confirmed"]
    return 1 if any(s in text for s in advance_signals) else 0

from ..llm import call_text_llm
from ..llm.prompts import build_planner_prompt
from .state import AgentState


async def run_planner(state: AgentState) -> list[str]:
    """
    Decompose the task into ordered sub-steps using a text-only LLM call.
    Returns a list of step strings. Falls back to [task] on any error.
    """
    try:
        prompt = build_planner_prompt(state.task, state.app_name)
        result = await call_text_llm(state.provider, prompt)
        steps = result.get("steps", [])
        if steps and isinstance(steps, list):
            return [str(s) for s in steps]
    except Exception as e:
        state.errors.append(f"Planner failed: {e}")

    return [state.task]

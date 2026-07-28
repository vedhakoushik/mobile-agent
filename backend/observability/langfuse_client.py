import os
import logging

logger = logging.getLogger(__name__)

_enabled = bool(os.environ.get("LANGFUSE_PUBLIC_KEY")) and bool(os.environ.get("LANGFUSE_SECRET_KEY"))
_client = None


def _get_client():
    global _client
    if not _enabled:
        return None
    if _client is None:
        try:
            from langfuse import Langfuse
            _client = Langfuse()  # reads LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST from env automatically
        except Exception as e:
            logger.warning(f"Langfuse client init failed, observability disabled: {e}")
            return None
    return _client


def start_session_trace(session_id: str, mode: str, app_name: str, task: str):
    """Starts a root span (acts as the trace) for one agent run, keyed deterministically
    by session_id so re-visiting the same session_id in Langfuse's UI groups correctly.
    Returns None if disabled or on any error — NEVER raises."""
    if not _enabled:
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        trace_id = client.create_trace_id(seed=session_id)
        span = client.start_observation(
            trace_context={"trace_id": trace_id},
            name=f"{mode}:{app_name}",
            as_type="span",
            input={"task": task},
            metadata={"session_id": session_id, "mode": mode, "app_name": app_name},
        )
        return span
    except Exception as e:
        logger.warning(f"Langfuse start_session_trace failed: {e}")
        return None


def log_generation(trace, provider: str, model_hint: str, prompt: str, response_dict: dict, usage: dict, latency_s: float, had_image: bool) -> None:
    """Logs one LLM call as a generation nested under `trace`. Fail-soft: never raises."""
    if not _enabled or trace is None:
        return
    try:
        prompt_text = prompt
        if had_image:
            prompt_text = prompt + "\n\n[+1 image, omitted]"
        # INVARIANT (not an oversight): resolved type_secret values never enter `decision`
        # or prompt strings anywhere in this codebase (see backend/security/ — secret
        # resolution happens only inside executor.py's action execution, after the LLM
        # call, never before it), so there is no secret-value redaction needed here beyond
        # omitting the raw image bytes above.
        usage_details = {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
        }
        gen = trace.start_observation(
            name=f"{provider}:{model_hint}",
            as_type="generation",
            input=prompt_text,
            output=response_dict,
            model=f"{provider}/{model_hint}",
            usage_details=usage_details,
            metadata={"latency_s": latency_s, "had_image": had_image},
        )
        gen.end()
    except Exception as e:
        logger.warning(f"Langfuse log_generation failed: {e}")


def end_session_trace(trace, status: str, task_complete: bool, round_num: int) -> None:
    """Closes out the session trace/span with final outcome. Fail-soft: never raises."""
    if not _enabled or trace is None:
        return
    try:
        trace.update(output={"status": status, "task_complete": task_complete, "round_num": round_num})
        trace.end()
        client = _get_client()
        if client is not None:
            client.flush()
    except Exception as e:
        logger.warning(f"Langfuse end_session_trace failed: {e}")

from ..llm.pricing import estimate_cost_usd


def record_usage(state, result: dict) -> dict:
    """Fold one LLM call's token usage into the session's running totals.

    Every LLM call in a session must go through this, otherwise it burns real
    tokens invisibly: it won't count toward max_tokens / max_cost_usd /
    max_llm_calls, and the cost reported for the session will understate what
    was actually spent. The planner, reflector and grid-mode calls all used to
    skip this — the reflector especially, since it's a two-image call made on
    every single Explore round.

    Pops "_usage" off `result` (mirroring what the agent loops already did
    inline) and returns the same dict for convenient chaining.
    """
    usage = result.pop("_usage", {}) if isinstance(result, dict) else {}
    state.llm_call_count += 1
    state.tokens_used += usage.get("total_tokens", 0)
    state.estimated_cost_usd += estimate_cost_usd(
        state.provider,
        usage.get("prompt_tokens", 0),
        usage.get("completion_tokens", 0),
    )
    return result

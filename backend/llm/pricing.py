import os

# Approximate USD cost per 1M tokens (input, output). These are placeholder
# figures — verify and update against each provider's actual current pricing
# page before relying on cost totals for anything real. Override via env vars
# if you have exact current numbers.
_DEFAULT_PRICING_PER_1M = {
    "gemini": (float(os.environ.get("PRICE_GEMINI_INPUT_PER_1M", "0.075")), float(os.environ.get("PRICE_GEMINI_OUTPUT_PER_1M", "0.30"))),
    "openai": (float(os.environ.get("PRICE_OPENAI_INPUT_PER_1M", "2.50")), float(os.environ.get("PRICE_OPENAI_OUTPUT_PER_1M", "10.00"))),
    "anthropic": (float(os.environ.get("PRICE_ANTHROPIC_INPUT_PER_1M", "3.00")), float(os.environ.get("PRICE_ANTHROPIC_OUTPUT_PER_1M", "15.00"))),
    "ollama": (0.0, 0.0),      # local, free
    "cerebras": (0.0, 0.0),    # free tier assumed — has no confirmed pricing here
    "glm": (0.0, 0.0),         # free tier assumed — has no confirmed pricing here
}


def estimate_cost_usd(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_price, output_price = _DEFAULT_PRICING_PER_1M.get(provider, (0.0, 0.0))
    return (prompt_tokens / 1_000_000) * input_price + (completion_tokens / 1_000_000) * output_price

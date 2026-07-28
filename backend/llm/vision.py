import asyncio
import json
import os
from typing import Any

import httpx


async def call_vision_llm(provider: str, screenshot_b64: str, prompt: str, trace=None) -> dict[str, Any]:
    """Single annotated screenshot + prompt → parsed JSON dict."""
    import time
    start = time.monotonic()
    if provider == "gemini":
        result = await _gemini_vision(screenshot_b64, prompt)
    elif provider == "openai":
        result = await _openai_vision(screenshot_b64, prompt)
    elif provider == "anthropic":
        result = await _anthropic_vision(screenshot_b64, prompt)
    elif provider == "ollama":
        result = await _ollama_vision(screenshot_b64, prompt)
    elif provider == "cerebras":
        result = await _cerebras_vision(screenshot_b64, prompt)
    elif provider == "glm":
        result = await _glm_vision(screenshot_b64, prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
    latency = time.monotonic() - start
    if trace is not None:
        from ..observability.langfuse_client import log_generation
        log_generation(trace, provider, "vision", prompt, result, result.get("_usage", {}), latency, had_image=True)
    return result


async def call_dual_vision_llm(
    provider: str,
    before_b64: str,
    after_b64: str,
    prompt: str,
    trace=None,
) -> dict[str, Any]:
    """Two screenshots (before + after) + prompt → parsed JSON dict."""
    if provider == "gemini":
        import time
        start = time.monotonic()
        result = await _gemini_dual_vision(before_b64, after_b64, prompt)
        latency = time.monotonic() - start
    elif provider == "openai":
        import time
        start = time.monotonic()
        result = await _openai_dual_vision(before_b64, after_b64, prompt)
        latency = time.monotonic() - start
    elif provider == "ollama":
        import time
        start = time.monotonic()
        result = await _ollama_dual_vision(before_b64, after_b64, prompt)
        latency = time.monotonic() - start
    elif provider == "cerebras":
        import time
        start = time.monotonic()
        result = await _cerebras_dual_vision(before_b64, after_b64, prompt)
        latency = time.monotonic() - start
    elif provider == "glm":
        import time
        start = time.monotonic()
        result = await _glm_dual_vision(before_b64, after_b64, prompt)
        latency = time.monotonic() - start
    else:
        return await call_vision_llm(provider, after_b64, prompt, trace=trace)
    if trace is not None:
        from ..observability.langfuse_client import log_generation
        log_generation(trace, provider, "dual_vision", prompt, result, result.get("_usage", {}), latency, had_image=True)
    return result


async def call_text_llm(provider: str, prompt: str, trace=None) -> dict[str, Any]:
    """Text-only LLM call → parsed JSON dict."""
    import time
    start = time.monotonic()
    if provider == "gemini":
        result = await _gemini_text(prompt)
    elif provider == "openai":
        result = await _openai_text(prompt)
    elif provider == "anthropic":
        result = await _anthropic_text(prompt)
    elif provider == "ollama":
        result = await _ollama_text(prompt)
    elif provider == "cerebras":
        result = await _cerebras_text(prompt)
    elif provider == "glm":
        result = await _glm_text(prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
    latency = time.monotonic() - start
    if trace is not None:
        from ..observability.langfuse_client import log_generation
        log_generation(trace, provider, "text", prompt, result, result.get("_usage", {}), latency, had_image=False)
    return result


# ── Gemini ────────────────────────────────────────────────────────────────────


_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def _gemini_request(parts: list[dict]) -> dict:
    """POST to Gemini REST, retrying on 429 (free-tier quota) and transient server
    errors (500/502/503/504 — Google's side, e.g. brief overload) alike."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={os.environ['GEMINI_API_KEY']}"
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    delays = [5, 15, 30]
    async with httpx.AsyncClient() as client:
        for attempt in range(len(delays) + 1):
            resp = await client.post(url, json=body, headers=headers, timeout=60.0)
            if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < len(delays):
                await asyncio.sleep(delays[attempt])
                continue
            break
    resp.raise_for_status()
    data = resp.json()
    result = _parse_json(data["candidates"][0]["content"]["parts"][0]["text"])
    usage = data.get("usageMetadata", {})
    result["_usage"] = {"prompt_tokens": usage.get("promptTokenCount", 0), "completion_tokens": usage.get("candidatesTokenCount", 0), "total_tokens": usage.get("totalTokenCount", 0)}
    return result


def _gemini_img(b64: str) -> dict:
    return {"inline_data": {"mime_type": "image/png", "data": b64}}


async def _gemini_vision(screenshot_b64: str, prompt: str) -> dict:
    return await _gemini_request([_gemini_img(screenshot_b64), {"text": prompt}])


async def _gemini_dual_vision(before_b64: str, after_b64: str, prompt: str) -> dict:
    return await _gemini_request([
        _gemini_img(before_b64),
        _gemini_img(after_b64),
        {"text": prompt},
    ])


async def _gemini_text(prompt: str) -> dict:
    return await _gemini_request([{"text": prompt}])


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _img_url(b64: str) -> dict:
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


async def _openai_vision(screenshot_b64: str, prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            _img_url(screenshot_b64),
            {"type": "text", "text": prompt},
        ]}],
    )
    result = _parse_json(resp.choices[0].message.content)
    u = getattr(resp, "usage", None)
    if u is not None:
        result["_usage"] = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0, "total_tokens": getattr(u, "total_tokens", 0) or 0}
    else:
        result["_usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return result


async def _openai_dual_vision(before_b64: str, after_b64: str, prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            _img_url(before_b64),
            _img_url(after_b64),
            {"type": "text", "text": prompt},
        ]}],
    )
    result = _parse_json(resp.choices[0].message.content)
    u = getattr(resp, "usage", None)
    if u is not None:
        result["_usage"] = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0, "total_tokens": getattr(u, "total_tokens", 0) or 0}
    else:
        result["_usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return result


async def _openai_text(prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    result = _parse_json(resp.choices[0].message.content)
    u = getattr(resp, "usage", None)
    if u is not None:
        result["_usage"] = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0, "total_tokens": getattr(u, "total_tokens", 0) or 0}
    else:
        result["_usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return result


# ── Anthropic ─────────────────────────────────────────────────────────────────

async def _anthropic_vision(screenshot_b64: str, prompt: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64}},
            {"type": "text", "text": prompt + "\n\nRespond with valid JSON only."},
        ]}],
    )
    result = _parse_json(resp.content[0].text)
    u = getattr(resp, "usage", None)
    input_t = getattr(u, "input_tokens", 0) or 0 if u else 0
    output_t = getattr(u, "output_tokens", 0) or 0 if u else 0
    result["_usage"] = {"prompt_tokens": input_t, "completion_tokens": output_t, "total_tokens": input_t + output_t}
    return result


async def _anthropic_text(prompt: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt + "\n\nRespond with valid JSON only."}],
    )
    result = _parse_json(resp.content[0].text)
    u = getattr(resp, "usage", None)
    input_t = getattr(u, "input_tokens", 0) or 0 if u else 0
    output_t = getattr(u, "output_tokens", 0) or 0 if u else 0
    result["_usage"] = {"prompt_tokens": input_t, "completion_tokens": output_t, "total_tokens": input_t + output_t}
    return result


# ── Ollama ────────────────────────────────────────────────────────────────────

async def _ollama_chat(model: str, prompt: str, images: list[str]) -> dict:
    """Native Ollama /api/chat — the OpenAI-compat /v1 layer ignores options.num_ctx,
    so screenshot prompts (~6k tokens) overflow the 4096 default and 400."""
    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/chat"
    # 8192 fits the ~6k-token screenshot prompts while staying GPU-resident on 8GB
    # cards; 16384 spills to CPU and inference crawls.
    num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))
    message: dict[str, Any] = {
        "role": "user",
        "content": prompt + "\n\nRespond with valid JSON only, no markdown fences.",
    }
    if images:
        message["images"] = images
    body = {
        "model": model,
        "messages": [message],
        "stream": False,
        "format": "json",
        "options": {"num_ctx": num_ctx},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=body, timeout=300.0)
    resp.raise_for_status()
    data = resp.json()
    result = _parse_json(data["message"]["content"])
    result["_usage"] = {"prompt_tokens": data.get("prompt_eval_count", 0) or 0, "completion_tokens": data.get("eval_count", 0) or 0, "total_tokens": (data.get("prompt_eval_count", 0) or 0) + (data.get("eval_count", 0) or 0)}
    return result


async def _ollama_vision(screenshot_b64: str, prompt: str) -> dict:
    model = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl")
    return await _ollama_chat(model, prompt, [screenshot_b64])


async def _ollama_dual_vision(before_b64: str, after_b64: str, prompt: str) -> dict:
    model = os.environ.get("OLLAMA_VISION_MODEL", "qwen2.5vl")
    return await _ollama_chat(model, prompt, [before_b64, after_b64])


async def _ollama_text(prompt: str) -> dict:
    model = os.environ.get("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
    return await _ollama_chat(model, prompt, [])


# ── Cerebras ──────────────────────────────────────────────────────────────────

async def _cerebras_text(prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="https://api.cerebras.ai/v1", api_key=os.environ["CEREBRAS_API_KEY"])
    model = os.environ.get("CEREBRAS_MODEL", "llama-3.3-70b")
    resp = await client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    result = _parse_json(resp.choices[0].message.content)
    u = getattr(resp, "usage", None)
    if u is not None:
        result["_usage"] = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0, "total_tokens": getattr(u, "total_tokens", 0) or 0}
    else:
        result["_usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return result


async def _cerebras_vision(screenshot_b64: str, prompt: str) -> dict:
    raise ValueError("Cerebras has no vision model — use gemini, glm, or ollama (with a vision model pulled) for screenshot-based calls")


async def _cerebras_dual_vision(before_b64: str, after_b64: str, prompt: str) -> dict:
    raise ValueError("Cerebras has no vision model — use gemini, glm, or ollama (with a vision model pulled) for screenshot-based calls")


# ── GLM ───────────────────────────────────────────────────────────────────────

async def _glm_vision(screenshot_b64: str, prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="https://open.bigmodel.cn/api/paas/v4", api_key=os.environ["GLM_API_KEY"])
    model = os.environ.get("GLM_VISION_MODEL", "glm-4v-flash")
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            _img_url(screenshot_b64),
            {"type": "text", "text": prompt},
        ]}],
    )
    result = _parse_json(resp.choices[0].message.content)
    u = getattr(resp, "usage", None)
    if u is not None:
        result["_usage"] = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0, "total_tokens": getattr(u, "total_tokens", 0) or 0}
    else:
        result["_usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return result


async def _glm_dual_vision(before_b64: str, after_b64: str, prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="https://open.bigmodel.cn/api/paas/v4", api_key=os.environ["GLM_API_KEY"])
    model = os.environ.get("GLM_VISION_MODEL", "glm-4v-flash")
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            _img_url(before_b64),
            _img_url(after_b64),
            {"type": "text", "text": prompt},
        ]}],
    )
    result = _parse_json(resp.choices[0].message.content)
    u = getattr(resp, "usage", None)
    if u is not None:
        result["_usage"] = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0, "total_tokens": getattr(u, "total_tokens", 0) or 0}
    else:
        result["_usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return result


async def _glm_text(prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(base_url="https://open.bigmodel.cn/api/paas/v4", api_key=os.environ["GLM_API_KEY"])
    model = os.environ.get("GLM_TEXT_MODEL", "glm-4-flash")
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    result = _parse_json(resp.choices[0].message.content)
    u = getattr(resp, "usage", None)
    if u is not None:
        result["_usage"] = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0, "total_tokens": getattr(u, "total_tokens", 0) or 0}
    else:
        result["_usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    text = text.strip()
    # strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {text[:200]}") from e

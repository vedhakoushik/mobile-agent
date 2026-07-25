import asyncio
import base64
import io
import json
import os
from typing import Any


async def call_vision_llm(provider: str, screenshot_b64: str, prompt: str) -> dict[str, Any]:
    """Single annotated screenshot + prompt → parsed JSON dict."""
    if provider == "gemini":
        return await _gemini_vision(screenshot_b64, prompt)
    elif provider == "openai":
        return await _openai_vision(screenshot_b64, prompt)
    elif provider == "anthropic":
        return await _anthropic_vision(screenshot_b64, prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def call_dual_vision_llm(
    provider: str,
    before_b64: str,
    after_b64: str,
    prompt: str,
) -> dict[str, Any]:
    """Two screenshots (before + after) + prompt → parsed JSON dict."""
    if provider == "gemini":
        return await _gemini_dual_vision(before_b64, after_b64, prompt)
    elif provider == "openai":
        return await _openai_dual_vision(before_b64, after_b64, prompt)
    else:
        return await call_vision_llm(provider, after_b64, prompt)


async def call_text_llm(provider: str, prompt: str) -> dict[str, Any]:
    """Text-only LLM call → parsed JSON dict."""
    if provider == "gemini":
        return await _gemini_text(prompt)
    elif provider == "openai":
        return await _openai_text(prompt)
    elif provider == "anthropic":
        return await _anthropic_text(prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# ── Gemini ────────────────────────────────────────────────────────────────────

def _b64_to_pil(b64: str):
    from PIL import Image
    return Image.open(io.BytesIO(base64.b64decode(b64)))


async def _gemini_vision(screenshot_b64: str, prompt: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    img = _b64_to_pil(screenshot_b64)
    resp = await asyncio.to_thread(model.generate_content, [img, prompt])
    return _parse_json(resp.text)


async def _gemini_dual_vision(before_b64: str, after_b64: str, prompt: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    before_img = _b64_to_pil(before_b64)
    after_img  = _b64_to_pil(after_b64)
    resp = await asyncio.to_thread(model.generate_content, [before_img, after_img, prompt])
    return _parse_json(resp.text)


async def _gemini_text(prompt: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={"response_mime_type": "application/json"},
    )
    resp = await asyncio.to_thread(model.generate_content, prompt)
    return _parse_json(resp.text)


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
    return _parse_json(resp.choices[0].message.content)


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
    return _parse_json(resp.choices[0].message.content)


async def _openai_text(prompt: str) -> dict:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = await client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(resp.choices[0].message.content)


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
    return _parse_json(resp.content[0].text)


async def _anthropic_text(prompt: str) -> dict:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = await client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt + "\n\nRespond with valid JSON only."}],
    )
    return _parse_json(resp.content[0].text)


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

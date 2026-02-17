"""Minimal OpenRouter client for server-side task execution.

This is intentionally small and dependency-free (httpx only), so it can be used
from background workers in production.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx


class OpenRouterError(RuntimeError):
    pass


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def chat_completion(
    *,
    model: str,
    prompt: str,
    timeout_s: float = 45.0,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Return (content, usage, meta).

    meta includes: status_code, elapsed_ms, provider_request_id, response_id.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is not configured")

    url = os.getenv("OPENROUTER_CHAT_URL", "https://openrouter.ai/api/v1/chat/completions").strip()
    if not url:
        raise OpenRouterError("OPENROUTER_CHAT_URL is empty")

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # Optional, but recommended by OpenRouter to attribute traffic.
    referer = (os.getenv("OPENROUTER_HTTP_REFERER") or os.getenv("PUBLIC_APP_URL") or "").strip()
    title = (os.getenv("OPENROUTER_X_TITLE") or "Coherence-Network").strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": float(os.getenv("OPENROUTER_TEMPERATURE", "0.2") or 0.2),
    }
    if _truthy(os.getenv("OPENROUTER_DISABLE_STREAM", "1")):
        payload["stream"] = False

    started = time.perf_counter()
    with httpx.Client(timeout=timeout_s, headers=headers) as client:
        resp = client.post(url, json=payload)
    elapsed_ms = int(round((time.perf_counter() - started) * 1000))

    status = int(resp.status_code)
    provider_request_id = (resp.headers.get("x-request-id") or resp.headers.get("x-openrouter-request-id") or "").strip()

    try:
        data = resp.json()
    except Exception:
        body_preview = (resp.text or "")[:500]
        raise OpenRouterError(f"OpenRouter response was not JSON (status={status}): {body_preview}")

    if status >= 400:
        err = data.get("error") if isinstance(data, dict) else None
        raise OpenRouterError(f"OpenRouter error (status={status}): {err or data}")

    if not isinstance(data, dict):
        raise OpenRouterError(f"Unexpected OpenRouter payload type: {type(data).__name__}")

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError("OpenRouter payload missing choices")

    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = (msg or {}).get("content") if isinstance(msg, dict) else None
    if not isinstance(content, str):
        raise OpenRouterError("OpenRouter payload missing message.content")

    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    response_id = str(data.get("id") or "")

    meta = {
        "status_code": status,
        "elapsed_ms": elapsed_ms,
        "provider_request_id": provider_request_id,
        "response_id": response_id,
    }
    return content, usage, meta


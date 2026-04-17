"""Attunement backends — concrete translators the view system can delegate to.

Register a backend at app startup via ``translator_service.set_backend(...)``.
When a caller requests ``attune_from_anchor()``, the backend renders title,
description, and markdown into the target language while carrying the
per-language glossary as frequency anchors.

Two backends ship:

- **LibreTranslateBackend** (default) — free, open-source, no API key.
  Calls a LibreTranslate instance (public ``libretranslate.com`` by default,
  self-hosted if ``COHERENCE_LIBRETRANSLATE_URL`` is set). Post-processes the
  translation to substitute the per-language glossary's felt-sense equivalents
  for anchor terms ("tending" → "hüten"), so the frequency carries through
  even though LibreTranslate is not prompt-aware.

- **AnthropicAttunementBackend** (optional) — Claude via httpx. Used when
  ``ANTHROPIC_API_KEY`` is present in the keystore or env; higher translation
  quality and native prompt steering, but requires a paid key.

``register_default_backend()`` prefers LibreTranslate (zero-config, free) and
falls through to Anthropic if a key is present. When nothing is configured,
no backend is installed and view endpoints serve anchor + pending_translation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Anthropic (optional, paid)
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT_SECONDS = 120

# ---------------------------------------------------------------------------
# LibreTranslate (default, free, no key)
# ---------------------------------------------------------------------------

DEFAULT_LIBRETRANSLATE_URL = "https://libretranslate.com"


_logger = logging.getLogger("coherence.translator")


def _read_keystore_key() -> str | None:
    """Read anthropic api key from ~/.coherence-network/keys.json when present."""
    path = Path.home() / ".coherence-network" / "keys.json"
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    for key in ("ANTHROPIC_API_KEY", "anthropic_api_key", "anthropic"):
        v = data.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            inner = v.get("api_key") or v.get("key") or v.get("token")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return None


def resolve_anthropic_key() -> str | None:
    key = _read_keystore_key()
    if key:
        return key
    env = os.getenv("ANTHROPIC_API_KEY")
    if env and env.strip():
        return env.strip()
    return None


# ---------------------------------------------------------------------------
# LibreTranslate backend — free, no key required
# ---------------------------------------------------------------------------

@dataclass
class LibreTranslateBackend:
    """Free translator backed by LibreTranslate + glossary post-processing.

    LibreTranslate is not prompt-aware, so the glossary_prompt parameter can't
    steer the model. Instead we load the glossary directly and substitute
    anchor-term renderings after the raw translation lands. This preserves
    the platform's frequency even when the underlying engine is basic.

    The public endpoint ``libretranslate.com`` rate-limits anonymous callers
    but works for the gentle pace of on-demand view attunement. For heavier
    use, self-host LibreTranslate and set ``COHERENCE_LIBRETRANSLATE_URL``.
    """

    base_url: str = DEFAULT_LIBRETRANSLATE_URL
    api_key: str | None = None  # optional — some instances require it
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def attune(
        self,
        *,
        source_markdown: str,
        source_title: str,
        source_description: str,
        source_lang: str,
        target_lang: str,
        glossary_prompt: str,  # unused — we apply glossary post-translation
    ) -> tuple[str, str, str]:
        t_title = self._translate(source_title, source_lang, target_lang) if source_title else ""
        t_desc = self._translate(source_description, source_lang, target_lang) if source_description else ""
        t_md = self._translate(source_markdown, source_lang, target_lang) if source_markdown else ""
        glossary = _load_glossary(target_lang)
        if glossary:
            t_title = _apply_glossary(t_title, glossary)
            t_desc = _apply_glossary(t_desc, glossary)
            t_md = _apply_glossary(t_md, glossary)
        return t_title, t_desc, t_md

    def _translate(self, text: str, source_lang: str, target_lang: str) -> str:
        if not text.strip():
            return text
        body: dict[str, Any] = {
            "q": text,
            "source": source_lang,
            "target": target_lang,
            "format": "text",
        }
        if self.api_key:
            body["api_key"] = self.api_key
        url = f"{self.base_url.rstrip('/')}/translate"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
                translated = data.get("translatedText") if isinstance(data, dict) else None
                if isinstance(translated, str) and translated.strip():
                    return translated
                _logger.warning("libretranslate returned unexpected shape: %r", data)
        except httpx.HTTPError as e:
            _logger.warning("libretranslate call failed: %s", e)
            try:
                from app.services import fallback_witness_service as _fw
                _fw.witness(
                    source="translator:libretranslate-http",
                    reason=f"libretranslate {type(e).__name__}; returning source text",
                    context={"target_lang": target_lang},
                )
            except Exception:
                pass
        # Fail-open: return source text so caller still has something
        return text


def _load_glossary(lang: str) -> list[tuple[str, str]]:
    """Read per-language glossary anchor terms for post-processing.

    Returns [(source_term, target_term)] ordered by source_term length
    descending, so multi-word terms match before single-word substrings.
    """
    try:
        from app.services import translation_cache_service as _cache
        entries = _cache.glossary_for(lang)
    except Exception:
        return []
    pairs = [(e.source_term, e.target_term) for e in entries if e.source_term and e.target_term]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _apply_glossary(text: str, glossary: list[tuple[str, str]]) -> str:
    """Substitute anchor-term renderings in the translated text.

    Case-aware word-boundary replacement. Doesn't touch words inside code
    fences, URLs, or markdown image syntax.
    """
    if not text:
        return text

    # Carve out regions we must NOT rewrite (code fences, inline code, URLs,
    # image-syntax prompts). We split the text into rewritable + preserve
    # segments, rewrite only the rewritable ones, then rejoin.
    PRESERVE_RE = re.compile(
        r"(```[\s\S]*?```|`[^`]+`|!\[[^\]]*\]\([^)]+\)|\[[^\]]*\]\([^)]+\)|https?://\S+)",
    )
    parts = PRESERVE_RE.split(text)
    rewritten: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # preserved segment (matched group) — leave untouched
            rewritten.append(part)
            continue
        segment = part
        for source_term, target_term in glossary:
            pattern = re.compile(rf"\b{re.escape(source_term)}\b", re.IGNORECASE)
            segment = pattern.sub(target_term, segment)
        rewritten.append(segment)
    return "".join(rewritten)


# ---------------------------------------------------------------------------
# Anthropic backend (optional upgrade)
# ---------------------------------------------------------------------------

@dataclass
class AnthropicAttunementBackend:
    """Calls Anthropic Messages API to attune source text into a target lang.

    Requires ``ANTHROPIC_API_KEY``. Higher translation quality and glossary
    is carried via the system prompt (not post-substitution), so terms land
    in grammatical context rather than as raw replacements.
    """

    api_key: str
    model: str = DEFAULT_ANTHROPIC_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = 8000

    def attune(
        self,
        *,
        source_markdown: str,
        source_title: str,
        source_description: str,
        source_lang: str,
        target_lang: str,
        glossary_prompt: str,
    ) -> tuple[str, str, str]:
        system = (
            "You are a translator who attunes text between languages. "
            "You carry the frequency of living relationship rather than policy-speak. "
            "Translate faithfully to meaning and voice, not word-for-word. "
            "Return a JSON object with exactly three string fields: title, description, markdown. "
            "Preserve the original markdown structure — headings, paragraphs, lists, blockquotes, "
            "image syntax like ![alt](visuals:prompt), and cross-reference lines like `→ lc-xxx`.\n\n"
            + (glossary_prompt or "")
        )
        user_payload = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "title": source_title,
            "description": source_description,
            "markdown": source_markdown,
        }
        user_message = (
            "Attune the following into the target language. Respond with JSON only, "
            "no prose around it.\n\n```json\n"
            + json.dumps(user_payload, ensure_ascii=False)
            + "\n```"
        )
        body = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_message}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            resp = client.post(ANTHROPIC_API_URL, headers=headers, json=body)
            resp.raise_for_status()
            data: Any = resp.json()
        parts = data.get("content") if isinstance(data, dict) else None
        if not isinstance(parts, list) or not parts:
            raise RuntimeError(f"Anthropic attunement: empty response: {data!r}")
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        parsed = _extract_json(text)
        title = str(parsed.get("title") or source_title)
        description = str(parsed.get("description") or source_description)
        markdown = str(parsed.get("markdown") or source_markdown)
        return title, description, markdown


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").lstrip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].lstrip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].rstrip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise RuntimeError(f"Anthropic attunement: could not parse JSON from response: {text[:200]!r}")


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def register_default_backend() -> str | None:
    """Install the best available backend. Returns the backend name or None.

    Resolution order:
      1. ``COHERENCE_TRANSLATOR=anthropic`` (explicit) + key present → Anthropic
      2. ``COHERENCE_TRANSLATOR=libretranslate`` (explicit) → LibreTranslate
      3. Default: LibreTranslate (free, no key)

    Called at app startup; safe to call multiple times (no-op when set).
    """
    from app.services import translator_service

    if translator_service.has_backend():
        return None

    choice = (os.getenv("COHERENCE_TRANSLATOR") or "").strip().lower()

    if choice == "anthropic":
        key = resolve_anthropic_key()
        if key:
            model = os.getenv("COHERENCE_TRANSLATOR_MODEL") or DEFAULT_ANTHROPIC_MODEL
            translator_service.set_backend(AnthropicAttunementBackend(api_key=key, model=model))
            return "anthropic"
        _logger.warning("COHERENCE_TRANSLATOR=anthropic but no key found — falling back to LibreTranslate")

    if choice == "libretranslate" or choice == "":
        url = os.getenv("COHERENCE_LIBRETRANSLATE_URL") or DEFAULT_LIBRETRANSLATE_URL
        api_key = os.getenv("COHERENCE_LIBRETRANSLATE_KEY") or None
        translator_service.set_backend(LibreTranslateBackend(base_url=url, api_key=api_key))
        return "libretranslate"

    _logger.warning("Unknown COHERENCE_TRANSLATOR=%r; no backend installed", choice)
    return None

"""Translator — renders a concept/idea/contribution into a target language
view, carrying the per-language glossary as the frequency spine.

Translation here is **attunement**: the translator (human or machine) listens
to the anchor view — whichever language was most recently touched by a human —
and renders that meaning into the target language, preferring the glossary's
felt-sense equivalents over clinical defaults.

This module is the pluggable edge. When the LLM backend is registered via
``set_backend()``, requesting a translation that doesn't exist yet will
attune it and write a new canonical view. When no backend is configured,
the caller is told pending_translation=true and the anchor view is returned
so the reader still meets the concept somewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.services import translation_cache_service as _cache


SUPPORTED_LOCALES: dict[str, dict[str, str]] = {
    "en": {"name": "English", "native_name": "English"},
    "de": {"name": "German", "native_name": "Deutsch"},
    "es": {"name": "Spanish", "native_name": "Español"},
    "id": {"name": "Indonesian", "native_name": "Bahasa Indonesia"},
}

DEFAULT_LOCALE = "en"


@dataclass
class ViewResponse:
    """What the concept router returns for a language view."""

    lang: str
    content_title: str
    content_description: str
    content_markdown: str
    content_hash: str
    author_type: str
    is_anchor: bool
    stale: bool
    translated_from_lang: str | None
    translated_from_hash: str | None
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "lang": self.lang,
            "content_title": self.content_title,
            "content_description": self.content_description,
            "content_markdown": self.content_markdown,
            "content_hash": self.content_hash,
            "author_type": self.author_type,
            "is_anchor": self.is_anchor,
            "stale": self.stale,
            "translated_from_lang": self.translated_from_lang,
            "translated_from_hash": self.translated_from_hash,
            "updated_at": self.updated_at,
        }


def list_locales() -> list[dict]:
    return [
        {"code": code, **meta, "default": code == DEFAULT_LOCALE}
        for code, meta in SUPPORTED_LOCALES.items()
    ]


def is_supported(lang: str | None) -> bool:
    return lang in SUPPORTED_LOCALES


def _view_to_response(
    rec: _cache.EntityViewRecord,
    anchor: _cache.EntityViewRecord | None,
) -> ViewResponse:
    return ViewResponse(
        lang=rec.lang,
        content_title=rec.content_title,
        content_description=rec.content_description,
        content_markdown=rec.content_markdown,
        content_hash=rec.content_hash,
        author_type=rec.author_type,
        is_anchor=(anchor is not None and rec.id == anchor.id),
        stale=_cache.is_stale(rec, anchor),
        translated_from_lang=rec.translated_from_lang,
        translated_from_hash=rec.translated_from_hash,
        updated_at=rec.updated_at.isoformat() if rec.updated_at else "",
    )


def load_view(
    *,
    entity_type: str,
    entity_id: str,
    lang: str,
) -> tuple[ViewResponse | None, ViewResponse | None]:
    """Return (requested_view, anchor_view). Either may be None if the entity
    has no views at all (fresh concept with no authored views yet).

    Both views are returned so the UI can show the requested language and, if
    it's stale or missing, also the anchor in its own language as the
    freshest expression available.
    """
    views = _cache.all_canonical_views(entity_type, entity_id)
    anchor = _cache.find_anchor(views)

    requested = next((v for v in views if v.lang == lang), None)
    req_resp = _view_to_response(requested, anchor) if requested else None
    anchor_resp = _view_to_response(anchor, anchor) if anchor else None
    return req_resp, anchor_resp


def build_glossary_prompt(lang: str) -> str:
    """Render the target language's anchor-term glossary as an LLM prompt
    fragment. Used by the translator backend before every attunement call.
    """
    entries = _cache.glossary_for(lang)
    if not entries:
        return ""
    native = SUPPORTED_LOCALES.get(lang, {}).get("native_name", lang)
    lines = [
        f"You are attuning this text into {native}.",
        "Carry the frequency of living relationship, not policy-speak. When "
        "the source uses the following anchor terms, prefer these renderings:",
    ]
    for e in entries:
        note = f" ({e.notes})" if e.notes else ""
        lines.append(f"- {e.source_term} → {e.target_term}{note}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pluggable attunement backend (future: LLM call)
# ---------------------------------------------------------------------------

class AttunementBackend(Protocol):
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
        """Return (title, description, markdown) rendered in target_lang."""
        ...


_BACKEND: AttunementBackend | None = None


def set_backend(backend: AttunementBackend | None) -> None:
    global _BACKEND
    _BACKEND = backend


def has_backend() -> bool:
    return _BACKEND is not None


def attune_from_anchor(
    *,
    entity_type: str,
    entity_id: str,
    target_lang: str,
    translator_model: str | None = None,
) -> ViewResponse | None:
    """Attune the anchor view into target_lang via the registered backend and
    write a new canonical view. Returns the new view, or None if no backend
    is configured.
    """
    if _BACKEND is None:
        return None
    views = _cache.all_canonical_views(entity_type, entity_id)
    anchor = _cache.find_anchor(views)
    if anchor is None:
        return None

    glossary = build_glossary_prompt(target_lang)
    title, desc, md = _BACKEND.attune(
        source_markdown=anchor.content_markdown,
        source_title=anchor.content_title,
        source_description=anchor.content_description,
        source_lang=anchor.lang,
        target_lang=target_lang,
        glossary_prompt=glossary,
    )
    rec = _cache.write_view(
        entity_type=entity_type,
        entity_id=entity_id,
        lang=target_lang,
        content_title=title,
        content_description=desc,
        content_markdown=md,
        author_type=_cache.AUTHOR_TYPE_TRANSLATION_MACHINE,
        translator_model=translator_model,
        translated_from_lang=anchor.lang,
        translated_from_hash=anchor.content_hash,
    )
    fresh_views = _cache.all_canonical_views(entity_type, entity_id)
    fresh_anchor = _cache.find_anchor(fresh_views)
    return _view_to_response(rec, fresh_anchor)


# ---------------------------------------------------------------------------
# In-memory snippet translation for transient content (news items, search
# results, ad-hoc labels). Does not write to entity_views — intended for
# content we don't own and can't stably identify, where a best-effort
# inline render is the right pattern.
# ---------------------------------------------------------------------------

_SNIPPET_CACHE: dict[tuple[str, str, str], tuple[str, str]] = {}
_SNIPPET_CACHE_MAX = 2000


def translate_snippet(
    title: str,
    description: str,
    source_lang: str,
    target_lang: str,
) -> tuple[str, str]:
    """Translate a (title, description) pair into ``target_lang`` via the
    registered backend. Returns the input unchanged when target == source
    or no backend is available.

    Results are memoized in-process to avoid repeat backend calls on the same
    transient snippet (RSS items, discovery feed labels) within a session.
    """
    if not target_lang or target_lang == source_lang:
        return title, description
    if _BACKEND is None:
        try:
            from app.services import fallback_witness_service as _fw
            _fw.witness(
                source="translator:no-backend",
                reason=f"No translator backend registered; returning source text for {target_lang}",
                context={"target_lang": target_lang},
            )
        except Exception:
            pass
        return title, description
    key = (source_lang, target_lang, f"{title}\x1f{description}")
    cached = _SNIPPET_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        t_title, t_desc, _ = _BACKEND.attune(
            source_markdown="",
            source_title=title or "",
            source_description=description or "",
            source_lang=source_lang,
            target_lang=target_lang,
            glossary_prompt=build_glossary_prompt(target_lang),
        )
    except Exception as e:
        try:
            from app.services import fallback_witness_service as _fw
            _fw.witness(
                source="translator:attune-failed",
                reason=f"Backend attune raised {type(e).__name__}; returning source text",
                context={"target_lang": target_lang},
            )
        except Exception:
            pass
        return title, description
    result = (t_title or title, t_desc or description)
    if len(_SNIPPET_CACHE) >= _SNIPPET_CACHE_MAX:
        _SNIPPET_CACHE.clear()
    _SNIPPET_CACHE[key] = result
    return result

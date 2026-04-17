"""Shared locale projection for API responses.

Every endpoint that returns user-facing text should meet the caller in the
caller's language. This module centralizes two concerns:

  1. **Locale resolution** — merge ``?lang=`` query param, ``Accept-Language``
     header, and default into a single caller locale.
  2. **Field projection** — given an entity (type, id) and a target locale,
     substitute ``name``/``title``/``description``/``body`` fields on a dict
     or Pydantic model from the canonical entity_view (when one exists).

Routers call ``resolve_caller_lang(request, query_lang)`` once per request
and then ``project(obj, entity_type, entity_id, lang)`` wherever they emit
user-visible text. The pattern scales to every entity with text in its
payload.
"""

from __future__ import annotations

from typing import Any, Iterable

from fastapi import Request

from app.services.localized_errors import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    caller_lang,
)


# Re-export so routers have a single import point.
__all__ = [
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "resolve_caller_lang",
    "project",
    "project_many",
    "project_fields",
]


def resolve_caller_lang(request: Request | None, query_lang: str | None = None) -> str:
    """Delegate to ``caller_lang`` — named so routers can see the intent."""
    return caller_lang(request, query_lang)


def _should_project(lang: str | None) -> bool:
    return bool(lang) and lang in SUPPORTED_LOCALES and lang != DEFAULT_LOCALE


def _set(obj: Any, field: str, value: str) -> None:
    if isinstance(obj, dict):
        obj[field] = value
        return
    try:
        setattr(obj, field, value)
    except Exception:
        pass


def _get(obj: Any, field: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(field)
    return getattr(obj, field, None)


def project(
    obj: Any,
    entity_type: str,
    entity_id: str,
    lang: str | None,
    *,
    title_field: str = "name",
    body_field: str = "description",
) -> Any:
    """Substitute ``title_field`` and ``body_field`` on ``obj`` from the canonical
    entity_view for ``(entity_type, entity_id, lang)``. Returns ``obj``.

    A missing view is a no-op — callers keep the anchor content. This lets the
    UI show a mix of fully-translated and not-yet-translated items without
    blocking on translation.
    """
    if not _should_project(lang):
        return obj
    # Lazy import to avoid pulling the cache into cold boot.
    from app.services import translation_cache_service as _tcache

    rec = _tcache.canonical_view(entity_type, entity_id, lang)
    if not rec or not rec.content_hash:
        return obj
    if rec.content_title:
        _set(obj, title_field, rec.content_title)
    if rec.content_description:
        _set(obj, body_field, rec.content_description)
    return obj


def project_many(
    items: Iterable[Any],
    entity_type: str,
    lang: str | None,
    *,
    id_field: str = "id",
    title_field: str = "name",
    body_field: str = "description",
) -> Iterable[Any]:
    """Project every item in the iterable. Items without an id are skipped."""
    if not _should_project(lang):
        return items
    for item in items:
        entity_id = _get(item, id_field)
        if entity_id:
            project(item, entity_type, str(entity_id), lang, title_field=title_field, body_field=body_field)
    return items


def project_fields(
    obj: Any,
    entity_type: str,
    entity_id: str,
    lang: str | None,
    field_map: dict[str, str],
) -> Any:
    """Variant for payloads that use non-standard field names.

    ``field_map`` maps canonical view fields to destination object fields,
    e.g. ``{"content_title": "label", "content_description": "summary"}``.
    """
    if not _should_project(lang):
        return obj
    from app.services import translation_cache_service as _tcache

    rec = _tcache.canonical_view(entity_type, entity_id, lang)
    if not rec or not rec.content_hash:
        return obj
    for src, dst in field_map.items():
        val = getattr(rec, src, None)
        if val:
            _set(obj, dst, val)
    return obj

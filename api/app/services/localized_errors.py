"""Localized API error messages.

HTTPException details are user-facing strings — they should meet the caller
in the caller's language. This module holds per-locale message bundles keyed
by a stable code and exposes ``localize(code, lang, **params)`` for the
routers to call when raising.

Bundles live inline in this module (not as JSON files) because the set is
small, tightly coupled to router code, and benefits from type-check-time
visibility when a code is added. New entries land here next to the routers
that raise them.

Locale resolution at the raise site:
    lang = caller_lang(request)    # Accept-Language header or ?lang= query
    raise HTTPException(status_code=404, detail=localize("concept_not_found", lang, id=cid))
"""

from __future__ import annotations

from typing import Any

from fastapi import Request


SUPPORTED_LOCALES = {"en", "de", "es", "id"}
DEFAULT_LOCALE = "en"


# ---------------------------------------------------------------------------
# Message bundles
# ---------------------------------------------------------------------------

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "concept_not_found": "Concept '{id}' not found",
        "concept_exists": "Concept '{id}' already exists",
        "concept_no_profile": "No profile for '{id}'",
        "concepts_not_found": "Concepts not found: {missing}",
        "target_concept_not_found": "Target concept '{id}' not found",
        "idea_not_found": "Idea '{id}' not found",
        "spec_not_found": "Spec '{id}' not found",
        "contributor_not_found": "Contributor '{id}' not found",
        "unsupported_locale": "Unsupported locale '{code}'",
        "unsupported_entity_type": "Unsupported entity_type '{type}'",
        "invalid_author_type": "Invalid author_type '{type}'",
        "translated_from_required": "translated_from_lang and translated_from_hash are required unless author_type is 'original_human'",
        "validation_failed": "Validation failed",
        "bad_request": "Bad request",
        "rate_limited": "Too many requests — please slow down",
        "unauthorized": "Authentication required",
        "forbidden": "Not allowed",
        "workspace_identity_required": "Workspace '{workspace}' requires a signed-in contributor (X-Contributor-Id)",
        "workspace_access_denied": "Not a member of workspace '{workspace}'",
        "unsupported_entity_type": "Reactions are not supported for entity type '{entity_type}'",
    },
    "de": {
        "concept_not_found": "Begriff '{id}' nicht gefunden",
        "concept_exists": "Begriff '{id}' existiert bereits",
        "concept_no_profile": "Kein Profil für '{id}'",
        "concepts_not_found": "Begriffe nicht gefunden: {missing}",
        "target_concept_not_found": "Ziel-Begriff '{id}' nicht gefunden",
        "idea_not_found": "Idee '{id}' nicht gefunden",
        "spec_not_found": "Entwurf '{id}' nicht gefunden",
        "contributor_not_found": "Mitwirkende Person '{id}' nicht gefunden",
        "unsupported_locale": "Nicht unterstützte Sprache '{code}'",
        "unsupported_entity_type": "Nicht unterstützter Entitäts-Typ '{type}'",
        "invalid_author_type": "Ungültiger author_type '{type}'",
        "translated_from_required": "translated_from_lang und translated_from_hash sind erforderlich, es sei denn author_type ist 'original_human'",
        "validation_failed": "Überprüfung fehlgeschlagen",
        "bad_request": "Fehlerhafte Anfrage",
        "rate_limited": "Zu viele Anfragen – bitte verlangsamen",
        "unauthorized": "Anmeldung erforderlich",
        "forbidden": "Nicht erlaubt",
        "workspace_identity_required": "Arbeitsbereich '{workspace}' benötigt eine angemeldete Identität (X-Contributor-Id)",
        "workspace_access_denied": "Nicht Mitglied des Arbeitsbereichs '{workspace}'",
        "unsupported_entity_type": "Reaktionen sind für Entitätstyp '{entity_type}' nicht unterstützt",
    },
    "es": {
        "concept_not_found": "Concepto '{id}' no encontrado",
        "concept_exists": "El concepto '{id}' ya existe",
        "concept_no_profile": "Sin perfil para '{id}'",
        "concepts_not_found": "Conceptos no encontrados: {missing}",
        "target_concept_not_found": "Concepto destino '{id}' no encontrado",
        "idea_not_found": "Idea '{id}' no encontrada",
        "spec_not_found": "Especificación '{id}' no encontrada",
        "contributor_not_found": "Contribuyente '{id}' no encontrado",
        "unsupported_locale": "Idioma no soportado '{code}'",
        "unsupported_entity_type": "Tipo de entidad no soportado '{type}'",
        "invalid_author_type": "author_type inválido '{type}'",
        "translated_from_required": "translated_from_lang y translated_from_hash son requeridos salvo que author_type sea 'original_human'",
        "validation_failed": "Validación fallida",
        "bad_request": "Solicitud incorrecta",
        "rate_limited": "Demasiadas solicitudes — por favor baja el ritmo",
        "unauthorized": "Autenticación requerida",
        "forbidden": "No permitido",
        "workspace_identity_required": "El espacio '{workspace}' requiere un contribuyente identificado (X-Contributor-Id)",
        "workspace_access_denied": "No eres miembro del espacio '{workspace}'",
        "unsupported_entity_type": "Las reacciones no están disponibles para el tipo de entidad '{entity_type}'",
    },
    "id": {
        "concept_not_found": "Gagasan konsep '{id}' tidak ditemukan",
        "concept_exists": "Konsep '{id}' sudah ada",
        "concept_no_profile": "Tidak ada profil untuk '{id}'",
        "concepts_not_found": "Konsep tidak ditemukan: {missing}",
        "target_concept_not_found": "Konsep tujuan '{id}' tidak ditemukan",
        "idea_not_found": "Gagasan '{id}' tidak ditemukan",
        "spec_not_found": "Rancangan '{id}' tidak ditemukan",
        "contributor_not_found": "Penyumbang '{id}' tidak ditemukan",
        "unsupported_locale": "Bahasa tidak didukung '{code}'",
        "unsupported_entity_type": "Tipe entitas tidak didukung '{type}'",
        "invalid_author_type": "author_type tidak sah '{type}'",
        "translated_from_required": "translated_from_lang dan translated_from_hash wajib kecuali author_type adalah 'original_human'",
        "validation_failed": "Validasi gagal",
        "bad_request": "Permintaan salah",
        "rate_limited": "Permintaan terlalu banyak — mohon pelankan",
        "unauthorized": "Autentikasi diperlukan",
        "forbidden": "Tidak diizinkan",
        "workspace_identity_required": "Ruang kerja '{workspace}' perlu kontributor yang masuk (X-Contributor-Id)",
        "workspace_access_denied": "Bukan anggota ruang kerja '{workspace}'",
        "unsupported_entity_type": "Reaksi tidak tersedia untuk tipe entitas '{entity_type}'",
    },
}


# ---------------------------------------------------------------------------
# Locale resolution from request
# ---------------------------------------------------------------------------

def caller_lang(request: Request | None, query_lang: str | None = None) -> str:
    """Resolve the caller's locale.

    Priority:
      1. ``query_lang`` (typically the ``?lang=`` query arg the endpoint already parses)
      2. ``Accept-Language`` header (first supported locale in the list)
      3. Default.
    """
    if query_lang and query_lang in SUPPORTED_LOCALES:
        return query_lang
    if request is not None:
        header = request.headers.get("accept-language")
        if header:
            # Parse in order: e.g. "de-DE,de;q=0.9,en;q=0.8"
            for part in header.split(","):
                code = part.split(";")[0].strip().lower()
                # Match "de-DE" or "de"
                root = code.split("-")[0]
                if root in SUPPORTED_LOCALES:
                    return root
    return DEFAULT_LOCALE


def localize(message_key: str, lang: str | None = None, **params: Any) -> str:
    """Format a message by key + locale. Falls back to English if missing.

    Unknown keys return the key itself — surfaces gaps as visible strings
    rather than silent empties.
    """
    target = lang if lang in SUPPORTED_LOCALES else DEFAULT_LOCALE
    bundle = MESSAGES.get(target) or MESSAGES[DEFAULT_LOCALE]
    template = bundle.get(message_key) or MESSAGES[DEFAULT_LOCALE].get(message_key) or message_key
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template

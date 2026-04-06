"""Shared failure taxonomy for consistent bucketing and signatures.

Patterns are loaded from the pipeline policy service (DB-backed with
in-memory cache).  Code defaults are used as fallback when the DB is
unavailable.  Patterns can be updated at runtime via the policy CRUD API.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

# Compiled-pattern cache: avoids re-compiling on every classify call.
# Invalidated whenever the underlying policy data changes.
_compiled_patterns: list[tuple[re.Pattern[str], str, str, str, str]] | None = None
_compiled_from_id: int | None = None  # id(list) used as cheap staleness check


def _load_patterns() -> list[tuple[re.Pattern[str], str, str, str, str]]:
    """Load failure patterns from the pipeline policy service and compile regexes.

    Uses a module-level cache keyed on the identity of the pattern list
    returned by the policy service, so recompilation only happens when the
    underlying data actually changes (at most once per cache TTL cycle).
    """
    global _compiled_patterns, _compiled_from_id

    try:
        from app.services import pipeline_policy_service
        raw: list[dict[str, str]] = pipeline_policy_service.get_failure_patterns()
    except Exception:
        raw = []

    # Fast path: same list object → patterns unchanged
    raw_id = id(raw)
    if _compiled_patterns is not None and _compiled_from_id == raw_id:
        return _compiled_patterns

    compiled: list[tuple[re.Pattern[str], str, str, str, str]] = []
    for entry in raw:
        try:
            compiled.append((
                re.compile(entry["regex"], re.I),
                entry["bucket"],
                entry["signature"],
                entry["summary"],
                entry["action"],
            ))
        except Exception as exc:
            log.warning("FAILURE_TAXONOMY bad pattern entry %s: %s", entry, exc)
            continue

    _compiled_patterns = compiled
    _compiled_from_id = raw_id
    return compiled


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _fallback_signature_suffix(text: str) -> str:
    lowered = _clean(text).lower()
    if not lowered:
        return "uncategorized"
    tokenized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    if not tokenized:
        return "uncategorized"
    words = [word for word in tokenized.split() if word and not word.isdigit()]
    compact = [word for word in words if len(word) >= 3 and not re.fullmatch(r"[0-9a-f]{8,}", word)]
    head = compact[:5] or words[:3]
    stem = "_".join(head)[:48] if head else "uncategorized"
    digest = hashlib.sha1(tokenized.encode("utf-8")).hexdigest()[:8]
    return f"{stem}_{digest}"


def classify_failure(
    *,
    output_text: str = "",
    result_error: str = "",
    failure_class: str = "",
) -> dict[str, str]:
    output = _clean(output_text)
    error = _clean(result_error)
    klass = _clean(failure_class)
    if not output and not error and not klass:
        return {
            "bucket": "empty_output",
            "signature": "empty_output",
            "summary": "Task failed without diagnostic output.",
            "action": "Capture stderr/stdout in task output and retry with explicit failure diagnostics enabled.",
        }

    combined = "\n".join(part for part in (output, error, klass) if part).strip()
    for pattern, bucket, signature, summary, action in _load_patterns():
        if pattern.search(combined):
            return {
                "bucket": bucket,
                "signature": signature,
                "summary": summary,
                "action": action,
            }

    return {
        "bucket": "other",
        "signature": f"other_{_fallback_signature_suffix(combined)}",
        "summary": "Failure did not match a known taxonomy signature; grouped by normalized fallback fingerprint.",
        "action": "Inspect failure output excerpt, add a concrete root-cause hypothesis, and retry with a minimal patch.",
    }


def is_paid_provider_blocked(
    *,
    output_text: str = "",
    result_error: str = "",
    failure_class: str = "",
) -> bool:
    classified = classify_failure(
        output_text=output_text,
        result_error=result_error,
        failure_class=failure_class,
    )
    signature = str(classified.get("signature") or "")
    if signature.startswith("paid_provider_"):
        return True
    return str(classified.get("bucket") or "") == "paid_provider_blocked"

"""Shared failure taxonomy for consistent bucketing and signatures."""

from __future__ import annotations

import hashlib
import re
from typing import Any


_PATTERNS: list[tuple[re.Pattern[str], str, str, str]] = [
    (
        re.compile(r"refresh_token_reused|failed to refresh token|codex_core::auth.*401 unauthorized", re.I),
        "auth",
        "oauth_refresh_token_reused",
        "OAuth refresh token became invalid/reused; session refresh and relogin path required.",
    ),
    (
        re.compile(r"paid provider and agent_allow_paid_providers is disabled", re.I),
        "paid_provider_blocked",
        "paid_provider_policy_disabled",
        "Paid provider route blocked by explicit policy flag.",
    ),
    (
        re.compile(r"paid-provider usage blocked by provider quota policy", re.I),
        "rate_limit",
        "paid_provider_quota_blocked",
        "Paid provider blocked by quota telemetry guard.",
    ),
    (
        re.compile(r"paid-provider usage blocked by window policy", re.I),
        "rate_limit",
        "paid_provider_window_budget_blocked",
        "Paid provider blocked by configured usage window budget.",
    ),
    (
        re.compile(
            r"unauthorized|forbidden|invalid api key|api key is not configured|status[=: ]40[13]|authentication",
            re.I,
        ),
        "auth",
        "auth_unauthorized_or_missing_credentials",
        "Authentication or authorization failed for required provider/session.",
    ),
    (
        re.compile(r"permission denied|errno 13|operation not permitted|read-only file system", re.I),
        "permissions",
        "file_or_runtime_permission_denied",
        "Runtime permission denied while reading/writing required files or directories.",
    ),
    (
        re.compile(r"rate limit|too many requests|status[=: ]429|http 429|quota exceeded|insufficient_quota", re.I),
        "rate_limit",
        "provider_rate_limit_or_quota",
        "Provider rate-limit or quota condition blocked execution.",
    ),
    (
        re.compile(r"timeout|timed out|gateway timeout", re.I),
        "timeout",
        "timeout_runtime_or_dependency",
        "Execution timed out before completion.",
    ),
    (
        re.compile(r"merge conflict|rebase|conflict \(content\)", re.I),
        "git_conflict",
        "git_conflict_or_rebase",
        "Git conflict or rebase conflict prevented execution progress.",
    ),
    (
        re.compile(r"assertionerror|test failed|pytest", re.I),
        "test_failure",
        "test_or_assertion_failure",
        "Validation/test assertion failed.",
    ),
    (
        re.compile(r"command not found|module not found|no module named|no such file or directory", re.I),
        "dependency_or_tooling",
        "missing_dependency_or_tool",
        "Missing dependency/tooling blocked execution.",
    ),
    (
        re.compile(r"empty direction|validation|status[=: ]422|unprocessable entity", re.I),
        "validation",
        "input_validation_failure",
        "Input validation failed before execution could proceed.",
    ),
    (
        re.compile(r"model_not_found|model not found|does not have access to model", re.I),
        "model_not_found",
        "model_unavailable_or_access_denied",
        "Requested model was unavailable or access was denied.",
    ),
    (
        re.compile(r"lease_owner_mismatch|lease_owned_by_other_worker|claim_failed|claim_conflict", re.I),
        "orchestration",
        "lease_or_claim_conflict",
        "Task lease/claim conflict prevented execution.",
    ),
]


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
        }

    combined = "\n".join(part for part in (output, error, klass) if part).strip()
    for pattern, bucket, signature, summary in _PATTERNS:
        if pattern.search(combined):
            return {
                "bucket": bucket,
                "signature": signature,
                "summary": summary,
            }

    return {
        "bucket": "other",
        "signature": f"other_{_fallback_signature_suffix(combined)}",
        "summary": "Failure did not match a known taxonomy signature; grouped by normalized fallback fingerprint.",
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

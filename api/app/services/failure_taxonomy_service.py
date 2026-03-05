"""Shared failure taxonomy for consistent bucketing and signatures."""

from __future__ import annotations

import hashlib
import re
from typing import Any


_PATTERNS: list[tuple[re.Pattern[str], str, str, str, str]] = [
    (
        re.compile(r"refresh_token_reused|failed to refresh token|codex_core::auth.*401 unauthorized", re.I),
        "auth",
        "oauth_refresh_token_reused",
        "OAuth refresh token became invalid/reused; session refresh and relogin path required.",
        "Refresh OAuth session on the runner, then retry with the same task id and preserved context.",
    ),
    (
        re.compile(r"paid provider and agent_allow_paid_providers is disabled", re.I),
        "paid_provider_blocked",
        "paid_provider_policy_disabled",
        "Paid provider route blocked by explicit policy flag.",
        "Route to an allowed OAuth CLI provider or explicitly set paid-provider override when intended.",
    ),
    (
        re.compile(r"paid-provider usage blocked by provider quota policy", re.I),
        "rate_limit",
        "paid_provider_quota_blocked",
        "Paid provider blocked by quota telemetry guard.",
        "Switch to an alternate model/provider with remaining quota and record a cooldown for the exhausted model.",
    ),
    (
        re.compile(r"paid-provider usage blocked by window policy", re.I),
        "rate_limit",
        "paid_provider_window_budget_blocked",
        "Paid provider blocked by configured usage window budget.",
        "Delay until the usage window resets or route to a cheaper model that still has budget.",
    ),
    (
        re.compile(
            r"unauthorized|forbidden|invalid api key|api key is not configured|status[=: ]40[13]|authentication",
            re.I,
        ),
        "auth",
        "auth_unauthorized_or_missing_credentials",
        "Authentication or authorization failed for required provider/session.",
        "Repair OAuth credentials/session for the target CLI and re-run a readiness check before retrying.",
    ),
    (
        re.compile(r"permission denied|errno 13|operation not permitted|read-only file system", re.I),
        "permissions",
        "file_or_runtime_permission_denied",
        "Runtime permission denied while reading/writing required files or directories.",
        "Fix workspace/runtime permissions (writable paths, ownership, or mount mode) and retry.",
    ),
    (
        re.compile(r"rate limit|too many requests|status[=: ]429|http 429|quota exceeded|insufficient_quota", re.I),
        "rate_limit",
        "provider_rate_limit_or_quota",
        "Provider rate-limit or quota condition blocked execution.",
        "Apply backoff or route to a different model/provider with available quota.",
    ),
    (
        re.compile(r"timeout|timed out|gateway timeout", re.I),
        "timeout",
        "timeout_runtime_or_dependency",
        "Execution timed out before completion.",
        "Reduce task scope, keep one concrete goal, and rerun targeted verification commands.",
    ),
    (
        re.compile(r"merge conflict|rebase|conflict \(content\)", re.I),
        "git_conflict",
        "git_conflict_or_rebase",
        "Git conflict or rebase conflict prevented execution progress.",
        "Resolve merge/rebase conflicts in the worktree, then retry from the same task context.",
    ),
    (
        re.compile(r"assertionerror|test failed|pytest", re.I),
        "test_failure",
        "test_or_assertion_failure",
        "Validation/test assertion failed.",
        "Use failing assertion output to patch implementation/spec verification and rerun focused tests.",
    ),
    (
        re.compile(r"command not found|module not found|no module named|no such file or directory", re.I),
        "dependency_or_tooling",
        "missing_dependency_or_tool",
        "Missing dependency/tooling blocked execution.",
        "Install or configure the missing tool/dependency and verify command availability before retry.",
    ),
    (
        re.compile(r"empty direction|validation|status[=: ]422|unprocessable entity", re.I),
        "validation",
        "input_validation_failure",
        "Input validation failed before execution could proceed.",
        "Provide required task inputs (direction, spec path, command contract) and retry.",
    ),
    (
        re.compile(r"model_not_found|model not found|does not have access to model", re.I),
        "model_not_found",
        "model_unavailable_or_access_denied",
        "Requested model was unavailable or access was denied.",
        "Switch to an accessible model and store the remap in model cooldown/selection metadata.",
    ),
    (
        re.compile(r"lease_owner_mismatch|lease_owned_by_other_worker|claim_failed|claim_conflict", re.I),
        "orchestration",
        "lease_or_claim_conflict",
        "Task lease/claim conflict prevented execution.",
        "Wait for existing lease expiry or reclaim with the same worker identity before retrying.",
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
            "action": "Capture stderr/stdout in task output and retry with explicit failure diagnostics enabled.",
        }

    combined = "\n".join(part for part in (output, error, klass) if part).strip()
    for pattern, bucket, signature, summary, action in _PATTERNS:
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

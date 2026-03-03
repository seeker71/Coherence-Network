from __future__ import annotations

import pytest

from app.services import failure_taxonomy_service


@pytest.mark.parametrize(
    ("output_text", "result_error", "bucket", "signature"),
    [
        (
            'ERROR codex_core::auth: Failed to refresh token: 401 Unauthorized: {"error":{"code":"refresh_token_reused"}}',
            "",
            "auth",
            "oauth_refresh_token_reused",
        ),
        (
            "Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled.",
            "",
            "paid_provider_blocked",
            "paid_provider_policy_disabled",
        ),
        (
            "Paid-provider usage blocked by provider quota policy: provider=openai-codex; monthly::credits remaining=4.0/100.0 ratio=0.04<=threshold=0.1",
            "",
            "rate_limit",
            "paid_provider_quota_blocked",
        ),
        (
            "Runtime failed: Module not found: playwright",
            "",
            "dependency_or_tooling",
            "missing_dependency_or_tool",
        ),
        (
            "Execution failed: [Errno 13] Permission denied: '/workspace/Coherence-Network/api/logs'",
            "",
            "permissions",
            "file_or_runtime_permission_denied",
        ),
        ("", "", "empty_output", "empty_output"),
    ],
)
def test_classify_failure_maps_similar_failures_to_consistent_signatures(
    output_text: str,
    result_error: str,
    bucket: str,
    signature: str,
) -> None:
    classified = failure_taxonomy_service.classify_failure(
        output_text=output_text,
        result_error=result_error,
    )
    assert classified["bucket"] == bucket
    assert classified["signature"] == signature
    assert str(classified["summary"] or "").strip()


def test_is_paid_provider_blocked_detects_all_paid_block_signatures() -> None:
    assert failure_taxonomy_service.is_paid_provider_blocked(
        output_text="Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled.",
    )
    assert failure_taxonomy_service.is_paid_provider_blocked(
        output_text="Paid-provider usage blocked by provider quota policy: provider=openai-codex",
    )
    assert failure_taxonomy_service.is_paid_provider_blocked(
        output_text="Paid-provider usage blocked by window policy: 8h_limit used=2/2, allowed=2 (fraction=1.0)",
    )


def test_classify_failure_unknown_message_gets_stable_fallback_signature() -> None:
    output = "Execution failed at weird subsystem: panic code ZXCV-123 while syncing ephemeral state"
    first = failure_taxonomy_service.classify_failure(output_text=output, result_error="")
    second = failure_taxonomy_service.classify_failure(output_text=output, result_error="")
    assert first["bucket"] == "other"
    assert first["signature"].startswith("other_")
    assert first["signature"] == second["signature"]

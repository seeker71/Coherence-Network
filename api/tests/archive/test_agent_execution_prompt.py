from __future__ import annotations

from app.services import agent_execution_service


def test_resolve_prompt_returns_direction_when_retry_context_missing() -> None:
    prompt = agent_execution_service._resolve_prompt(  # pyright: ignore[reportPrivateUsage]
        {
            "direction": "Implement deterministic slug utility",
            "context": {},
        }
    )
    assert prompt == "Implement deterministic slug utility"


def test_resolve_prompt_includes_retry_memory_packet() -> None:
    prompt = agent_execution_service._resolve_prompt(  # pyright: ignore[reportPrivateUsage]
        {
            "direction": "Fix review failures without restarting",
            "context": {
                "retry_hint": "Apply the smallest patch that fixes failing acceptance criteria.",
                "last_failure_category": "test_failure",
                "last_failure_signature": "test_or_assertion_failure",
                "last_failure_summary": "Validation/test assertion failed.",
                "last_failure_action": "Use failing assertions to patch implementation and rerun focused tests.",
                "last_failure_output": "PASS_FAIL: FAIL PATCH_GUIDANCE: update slug normalization edge case.",
                "retry_reflections": [
                    {
                        "retry_number": 1,
                        "blind_spot": "Acceptance criteria edge case was skipped.",
                        "next_action": "Patch edge case handling and rerun verification script.",
                    }
                ],
            },
        }
    )
    assert "Retry guidance:" in prompt
    assert "Retry memory packet:" in prompt
    assert "Preserve prior work and patch incrementally" in prompt
    assert "last_failure_signature=test_or_assertion_failure" in prompt
    assert "last_failure_output_excerpt=PASS_FAIL: FAIL PATCH_GUIDANCE" in prompt

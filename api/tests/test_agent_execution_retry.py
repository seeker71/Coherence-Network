from __future__ import annotations

from app.services import agent_execution_retry


def test_resolve_retry_max_allows_explicit_zero() -> None:
    resolved = agent_execution_retry._resolve_retry_max(  # pyright: ignore[reportPrivateUsage]
        {"retry_max": 0},
        3,
    )
    assert resolved == 0


def test_record_failure_hits_does_not_retry_when_retry_max_zero() -> None:
    updates: list[dict] = []
    execute_calls: list[dict] = []

    def _update_task(_task_id: str, **kwargs) -> None:
        updates.append(kwargs)

    def _execute_again(_task_id: str, **kwargs) -> dict:
        execute_calls.append(kwargs)
        return {"status": "failed", "error": "should_not_retry"}

    task = {"context": {"retry_max": 0}, "output": "auth failed", "model": "codex/gpt-5-codex"}
    result = {"status": "failed", "error": "auth"}
    finalized = agent_execution_retry.record_failure_hits_and_retry(
        task_id="task_no_retry",
        task=task,
        result=result,
        worker_id="worker:test",
        retry_depth=0,
        env_retry_max=3,
        pending_status="pending",
        update_task=_update_task,
        execute_again=_execute_again,
        force_paid_providers=False,
        max_cost_usd=None,
        estimated_cost_usd=None,
        cost_slack_ratio=None,
    )

    assert finalized == result
    assert execute_calls == []
    assert updates
    context = updates[-1].get("context") or {}
    assert context.get("retry_max") == 0
    assert "retry_count" not in context


def test_failure_category_uses_shared_taxonomy_for_paid_provider_blocks() -> None:
    category = agent_execution_retry._failure_category(  # pyright: ignore[reportPrivateUsage]
        "Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled.",
        "",
    )
    assert category == "paid_provider_blocked"

    category_quota = agent_execution_retry._failure_category(  # pyright: ignore[reportPrivateUsage]
        "Paid-provider usage blocked by provider quota policy: provider=openai-codex",
        "",
    )
    assert category_quota == "paid_provider_blocked"


def test_failure_category_preserves_generic_rate_limit_classification() -> None:
    category = agent_execution_retry._failure_category(  # pyright: ignore[reportPrivateUsage]
        "OpenRouter request failed with HTTP 429 Too Many Requests",
        "",
    )
    assert category == "rate_limit"

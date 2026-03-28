"""Tests for Spec 109: Open Responses Interoperability Layer.

Verifies:
1. NormalizedResponseCall schema accepts valid data and rejects invalid data.
2. normalize_to_open_responses produces open_responses_v1 records for multiple providers.
3. Route/model evidence is persisted per task so operator audits can verify execution paths.
4. provider_usage_service log is isolated between test calls via clear_call_log().
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Schema tests — NormalizedResponseCall
# ---------------------------------------------------------------------------


def test_normalized_response_call_schema_valid() -> None:
    """NormalizedResponseCall accepts all required fields with valid data."""
    from app.models.schemas import NormalizedResponseCall

    call = NormalizedResponseCall(
        task_id="task_abc",
        provider="claude",
        model="claude-sonnet-4-6",
        request_schema="open_responses_v1",
        output_text="some output",
    )

    assert call.task_id == "task_abc"
    assert call.provider == "claude"
    assert call.model == "claude-sonnet-4-6"
    assert call.request_schema == "open_responses_v1"
    assert call.output_text == "some output"


def test_normalized_response_call_request_schema_is_literal() -> None:
    """request_schema field is always 'open_responses_v1' and cannot be overridden."""
    from app.models.schemas import NormalizedResponseCall

    call = NormalizedResponseCall(
        task_id="task_x",
        provider="gemini",
        model="gemini-pro",
        output_text="",
    )
    assert call.request_schema == "open_responses_v1"


def test_normalized_response_call_output_text_defaults_to_empty() -> None:
    """output_text defaults to empty string when not provided."""
    from app.models.schemas import NormalizedResponseCall

    call = NormalizedResponseCall(
        task_id="task_default",
        provider="codex",
        model="gpt-4o",
    )
    assert call.output_text == ""


def test_normalized_response_call_rejects_empty_task_id() -> None:
    """task_id with empty string fails validation (min_length=1)."""
    from app.models.schemas import NormalizedResponseCall

    with pytest.raises(ValidationError):
        NormalizedResponseCall(
            task_id="",
            provider="claude",
            model="claude-sonnet-4-6",
        )


def test_normalized_response_call_rejects_empty_provider() -> None:
    """provider with empty string fails validation (min_length=1)."""
    from app.models.schemas import NormalizedResponseCall

    with pytest.raises(ValidationError):
        NormalizedResponseCall(
            task_id="task_y",
            provider="",
            model="claude-sonnet-4-6",
        )


def test_normalized_response_call_rejects_empty_model() -> None:
    """model with empty string fails validation (min_length=1)."""
    from app.models.schemas import NormalizedResponseCall

    with pytest.raises(ValidationError):
        NormalizedResponseCall(
            task_id="task_z",
            provider="claude",
            model="",
        )


def test_normalized_response_call_model_dump_includes_all_fields() -> None:
    """model_dump() produces a dict with all five schema fields."""
    from app.models.schemas import NormalizedResponseCall

    call = NormalizedResponseCall(
        task_id="task_dump",
        provider="openrouter",
        model="openrouter/mistral-7b",
        output_text="dumped",
    )
    d = call.model_dump()
    assert set(d.keys()) == {"task_id", "provider", "model", "request_schema", "output_text"}
    assert d["request_schema"] == "open_responses_v1"


# ---------------------------------------------------------------------------
# Adapter tests — normalize_to_open_responses
# ---------------------------------------------------------------------------


def test_normalize_adapter_returns_normalized_response_call() -> None:
    """normalize_to_open_responses returns a NormalizedResponseCall instance."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc
    from app.models.schemas import NormalizedResponseCall

    pu_svc.clear_call_log()

    result = svc.normalize_to_open_responses(
        task_id="task_type_check",
        provider="claude",
        model="claude-haiku-4-5-20251001",
        output_text="hello",
    )

    assert isinstance(result, NormalizedResponseCall)


def test_normalize_adapter_claude_provider() -> None:
    """Claude provider produces open_responses_v1 record without prompt rewrite."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    result = svc.normalize_to_open_responses(
        task_id="task_109_claude",
        provider="claude",
        model="claude-sonnet-4-6",
        output_text="claude response",
    )

    assert result.request_schema == "open_responses_v1"
    assert result.provider == "claude"
    assert result.model == "claude-sonnet-4-6"
    assert result.output_text == "claude response"


def test_normalize_adapter_codex_provider() -> None:
    """Codex provider produces open_responses_v1 record without prompt rewrite."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    result = svc.normalize_to_open_responses(
        task_id="task_109_codex",
        provider="codex",
        model="gpt-4o",
        output_text="codex response",
    )

    assert result.request_schema == "open_responses_v1"
    assert result.provider == "codex"
    assert result.model == "gpt-4o"


def test_normalize_adapter_gemini_provider() -> None:
    """Gemini provider also routes through the same normalized interface."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    result = svc.normalize_to_open_responses(
        task_id="task_109_gemini",
        provider="gemini",
        model="gemini-pro",
        output_text="gemini response",
    )

    assert result.request_schema == "open_responses_v1"
    assert result.provider == "gemini"


def test_normalize_adapter_default_output_text_is_empty() -> None:
    """output_text defaults to empty string when omitted from normalize call."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    result = svc.normalize_to_open_responses(
        task_id="task_109_notext",
        provider="claude",
        model="claude-haiku-4-5-20251001",
    )

    assert result.output_text == ""


# ---------------------------------------------------------------------------
# Audit / persistence tests — provider_usage_service
# ---------------------------------------------------------------------------


def test_audit_log_persists_route_evidence() -> None:
    """Each normalize call appends a record with route/model evidence to the log."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    svc.normalize_to_open_responses(
        task_id="task_audit_1",
        provider="claude",
        model="claude-sonnet-4-6",
        output_text="audit test",
    )

    log = pu_svc.get_call_log()
    assert len(log) == 1
    entry = log[0]
    assert entry["task_id"] == "task_audit_1"
    assert entry["provider"] == "claude"
    assert entry["model"] == "claude-sonnet-4-6"
    assert entry["request_schema"] == "open_responses_v1"


def test_audit_log_accumulates_across_multiple_providers() -> None:
    """Audit log accumulates entries across all providers; each carries open_responses_v1."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    calls = [
        ("task_multi_1", "claude", "claude-sonnet-4-6"),
        ("task_multi_2", "codex", "gpt-4o-mini"),
        ("task_multi_3", "gemini", "gemini-pro"),
    ]
    for task_id, provider, model in calls:
        svc.normalize_to_open_responses(task_id=task_id, provider=provider, model=model)

    log = pu_svc.get_call_log()
    assert len(log) == 3

    for entry in log:
        assert entry["request_schema"] == "open_responses_v1"

    providers_in_log = {e["provider"] for e in log}
    assert providers_in_log == {"claude", "codex", "gemini"}


def test_audit_log_get_call_log_for_task_isolates_by_task_id() -> None:
    """get_call_log_for_task returns only entries matching the requested task_id."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    svc.normalize_to_open_responses(task_id="task_iso_a", provider="claude", model="m1")
    svc.normalize_to_open_responses(task_id="task_iso_b", provider="codex", model="m2")
    svc.normalize_to_open_responses(task_id="task_iso_a", provider="gemini", model="m3")

    log_a = pu_svc.get_call_log_for_task("task_iso_a")
    log_b = pu_svc.get_call_log_for_task("task_iso_b")

    assert len(log_a) == 2
    assert len(log_b) == 1
    assert all(e["task_id"] == "task_iso_a" for e in log_a)
    assert log_b[0]["task_id"] == "task_iso_b"


def test_audit_log_clear_resets_state() -> None:
    """clear_call_log() empties the in-memory log for test isolation."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    svc.normalize_to_open_responses(task_id="task_before_clear", provider="claude", model="m1")
    assert len(pu_svc.get_call_log()) >= 1

    pu_svc.clear_call_log()
    assert pu_svc.get_call_log() == []


def test_audit_log_get_call_log_returns_copy() -> None:
    """get_call_log() returns a copy; mutating it does not affect the internal log."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()
    svc.normalize_to_open_responses(task_id="task_copy", provider="claude", model="m1")

    log = pu_svc.get_call_log()
    log.clear()  # mutate returned list

    assert len(pu_svc.get_call_log()) == 1  # internal log unchanged


def test_audit_log_entry_has_all_schema_fields() -> None:
    """Each persisted entry contains all five NormalizedResponseCall fields."""
    import app.services.agent_service as svc
    import app.services.provider_usage_service as pu_svc

    pu_svc.clear_call_log()

    svc.normalize_to_open_responses(
        task_id="task_fields",
        provider="codex",
        model="gpt-4o",
        output_text="field check",
    )

    log = pu_svc.get_call_log()
    assert len(log) == 1
    entry = log[0]
    assert set(entry.keys()) == {"task_id", "provider", "model", "request_schema", "output_text"}

from __future__ import annotations

from app.services import failure_taxonomy_service
from app.services import pipeline_policy_service
from app.services.agent_service_pipeline_status import _pipeline_queue_diagnostics
from app.services.agent_service_store import _store
from app.services.agent_service_task_derive import failure_classification


def test_failure_patterns_merge_code_defaults_with_database_override(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline_policy_service,
        "get_policy",
        lambda key, default: [
            {
                "regex": "custom-provider-error",
                "bucket": "provider_error",
                "signature": "custom_provider_error",
                "summary": "Custom provider error.",
                "action": "Use the custom provider repair path.",
            }
        ],
    )

    patterns = pipeline_policy_service.get_failure_patterns()
    signatures = {row["signature"] for row in patterns}

    assert "custom_provider_error" in signatures
    assert "impl_without_active_spec" in signatures
    assert "provider_claimed_success_no_diff" in signatures


def test_failure_taxonomy_names_spec_gate_and_hollow_success(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_policy_service, "get_policy", lambda key, default: default)
    failure_taxonomy_service._compiled_patterns = None
    failure_taxonomy_service._compiled_from_id = None

    spec_gate = failure_taxonomy_service.classify_failure(
        failure_class="other_spec_gate_impl_for_cli_87995841"
    )
    hollow = failure_taxonomy_service.classify_failure(
        output_text="Provider claimed success but produced no code changes"
    )

    assert spec_gate["bucket"] == "spec_gate"
    assert spec_gate["signature"] == "impl_without_active_spec"
    assert hollow["bucket"] == "no_code"
    assert hollow["signature"] == "provider_claimed_success_no_diff"


def test_failure_taxonomy_names_compaction_and_progress_only_outputs(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_policy_service, "get_policy", lambda key, default: default)
    failure_taxonomy_service._compiled_patterns = None
    failure_taxonomy_service._compiled_from_id = None

    compacted = failure_taxonomy_service.classify_failure(
        failure_class="other_compact_summary_original_chars_start_a2f76de1"
    )
    progress_only = failure_taxonomy_service.classify_failure(
        failure_class="other_now_researching_the_idea_and_9bad7518"
    )

    assert compacted["bucket"] == "context_compaction"
    assert compacted["signature"] == "context_compaction_summary_leaked"
    assert progress_only["bucket"] == "no_code"
    assert progress_only["signature"] == "progress_only_no_artifact"


def test_failure_classification_can_re_digest_stored_signature(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_policy_service, "get_policy", lambda key, default: default)
    failure_taxonomy_service._compiled_patterns = None
    failure_taxonomy_service._compiled_from_id = None

    classified = failure_classification({
        "output": "",
        "context": {
            "failure_reason_bucket": "other",
            "failure_signature": "other_done_spec_gate_impl_for_5620d8da",
        },
    })

    assert classified["bucket"] == "done_spec_gate"
    assert classified["signature"] == "impl_for_done_spec"


def test_pipeline_diagnostics_reads_recent_failed_tasks_outside_activity_window(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_policy_service, "get_policy", lambda key, default: default)
    failure_taxonomy_service._compiled_patterns = None
    failure_taxonomy_service._compiled_from_id = None
    original_store = dict(_store)
    try:
        _store.clear()
        _store["task_failed"] = {
            "id": "task_failed",
            "status": "failed",
            "task_type": "impl",
            "created_at": None,
            "updated_at": None,
            "output": "",
            "context": {
                "failure_reason_bucket": "other",
                "failure_signature": "other_spec_gate_impl_for_cli_87995841",
            },
        }

        diagnostics = _pipeline_queue_diagnostics(
            running=[],
            pending=[],
            completed=[{"id": f"task_completed_{idx}"} for idx in range(12)],
        )
    finally:
        _store.clear()
        _store.update(original_store)

    assert diagnostics["recent_failed_count"] == 1
    assert diagnostics["recent_failed_reasons"] == [{"reason": "spec_gate", "count": 1}]
    assert diagnostics["recent_failed_signatures"] == [
        {"signature": "impl_without_active_spec", "count": 1}
    ]

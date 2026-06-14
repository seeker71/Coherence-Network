from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.routers import models as models_router


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_model_routes_normalize_current_config_shape(tmp_path: Path, monkeypatch) -> None:
    routing_path = tmp_path / "api" / "config" / "model_routing.json"
    _write_json(
        routing_path,
        {
            "task_type_tier": {"impl": "strong", "review": "fast"},
            "tiers_by_executor": {
                "codex": {"strong": "gpt-5.3-codex-spark", "fast": "gpt-5.3-codex-spark"},
                "gemini": {"strong": "gemini-2.5-pro", "fast": "gemini-2.5-flash"},
            },
            "openrouter_models_by_task_type": {"impl": "openrouter/free"},
            "fallback_chains": {"gemini": ["gemini-2.5-pro", "gemini-2.5-flash"]},
        },
    )
    monkeypatch.setattr(models_router, "_ROUTING_PATH", routing_path)

    listing = asyncio.run(models_router.list_models())
    routing = asyncio.run(models_router.get_routing_config())

    assert listing.total == 5
    assert listing.executors["codex"][0].model_id == "gpt-5.3-codex-spark"
    assert routing.executor_tiers["gemini"]["fast"] == ["gemini-2.5-flash"]
    assert routing.openrouter_task_overrides == {"impl": "openrouter/free"}


def test_learning_dashboard_exposes_models_receipts_and_guidance(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    routing_path = repo_root / "api" / "config" / "model_routing.json"
    evidence_dir = repo_root / "docs" / "system_audit"
    proof_dir = evidence_dir / "model_executor_run_ledger"
    native_receipt_dir = evidence_dir / "native_training_receipts"
    _write_json(
        routing_path,
        {
            "task_type_tier": {"impl": "strong"},
            "tiers_by_executor": {"codex": {"strong": "gpt-5.3-codex-spark"}},
            "fallback_chains": {"codex": ["gpt-5.3-codex-spark"]},
        },
    )
    _write_json(
        evidence_dir / "commit_evidence_2026-06-14_model_learning.json",
        {
            "commit_scope": "Add a model learning proof floor.",
            "idea_ids": ["form-native-model-data-as-cells"],
            "spec_ids": ["coherence-substrate-model-vitality"],
            "task_ids": ["model-learning-floor"],
            "local_validation": {"status": "pass", "commands": ["pytest focused"]},
            "e2e_validation": {"status": "pass", "summary": "Proof floor is readable."},
            "phase_gate": {"state": "local-proof-pass", "next": "Attach weight receipts."},
            "evidence_refs": ["form/form-stdlib/model-vitality.fk"],
        },
    )
    _write_json(
        proof_dir / "model-learning-floor.json",
        {
            "run_id": "model-learning-floor",
            "model_used": "gpt-5-codex",
            "pass_fail": "pass",
            "attempts": 1,
            "commands_run": ["pytest focused"],
            "source": {"path": "docs/system_audit/commit_evidence_2026-06-14_model_learning.json"},
        },
    )

    monkeypatch.setattr(models_router, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(models_router, "_ROUTING_PATH", routing_path)
    monkeypatch.setattr(models_router, "_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(models_router, "_PROOF_LEDGER_DIR", proof_dir)
    monkeypatch.setattr(models_router, "_NATIVE_TRAINING_RECEIPT_DIR", native_receipt_dir)

    dashboard = asyncio.run(models_router.get_learning_dashboard())

    assert dashboard.summary.routed_model_count == 1
    assert dashboard.summary.learning_surface_count == 1
    assert dashboard.summary.proof_pass_count == 1
    assert dashboard.summary.trained_native_model_count == 0
    assert dashboard.native_training_artifacts == []
    assert dashboard.learning_surfaces[0].surface_id == "model-learning-floor"
    assert dashboard.learning_surfaces[0].training_metadata["trained_native_weights"] is False
    assert dashboard.learning_surfaces[0].next_step == "Attach weight receipts."
    assert dashboard.recent_proof_runs[0].model_used == "gpt-5-codex"


def test_learning_dashboard_counts_committed_native_training_receipts(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path
    routing_path = repo_root / "api" / "config" / "model_routing.json"
    evidence_dir = repo_root / "docs" / "system_audit"
    proof_dir = evidence_dir / "model_executor_run_ledger"
    native_receipt_dir = evidence_dir / "native_training_receipts"
    _write_json(routing_path, {"tiers_by_executor": {}})
    _write_json(
        native_receipt_dir / "form-native-nearest-shape-v0.json",
        {
            "artifact_id": "form-native-nearest-shape-v0",
            "artifact_kind": "nearest-shape-prototype",
            "model_family": "Form-native nearest-shape",
            "status": "active",
            "recipe_path": "form/form-stdlib/native-training-receipt.fk",
            "proof_band_path": "form/form-stdlib/tests/native-training-receipt-band.fk",
            "observed_at": "2026-06-14T00:00:00Z",
            "continuous_cycle_count": 1,
            "weights": {"hash": "sha256:weights"},
            "data": {"hash": "sha256:data", "sample_count": 6},
            "eval": {
                "hash": "sha256:eval",
                "heldout_count": 4,
                "correct_count": 4,
                "wrong_count": 0,
                "native_accuracy_ppm": 1000000,
                "oracle_accuracy_ppm": 750000,
            },
            "training": {"native_beats_oracle": True},
            "validation": {"status": "pass"},
        },
    )
    _write_json(
        native_receipt_dir / "pending.json",
        {
            "artifact_id": "pending",
            "status": "pending",
            "weights": {"hash": "sha256:weights"},
            "data": {"hash": "sha256:data", "sample_count": 1},
            "eval": {"hash": "sha256:eval", "heldout_count": 1, "correct_count": 1, "wrong_count": 0},
            "validation": {"status": "pending"},
        },
    )

    monkeypatch.setattr(models_router, "_REPO_ROOT", repo_root)
    monkeypatch.setattr(models_router, "_ROUTING_PATH", routing_path)
    monkeypatch.setattr(models_router, "_EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(models_router, "_PROOF_LEDGER_DIR", proof_dir)
    monkeypatch.setattr(models_router, "_NATIVE_TRAINING_RECEIPT_DIR", native_receipt_dir)

    dashboard = asyncio.run(models_router.get_learning_dashboard())

    assert dashboard.summary.trained_native_model_count == 1
    assert dashboard.native_training_artifacts[0].artifact_id == "form-native-nearest-shape-v0"
    assert dashboard.native_training_artifacts[0].weights_hash == "sha256:weights"
    assert dashboard.native_training_artifacts[0].native_beats_oracle is True

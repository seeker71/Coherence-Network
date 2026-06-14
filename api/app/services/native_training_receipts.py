"""Load committed native training receipt artifacts for model dashboards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class NativeTrainingArtifact(BaseModel):
    artifact_id: str
    artifact_kind: str
    model_family: str
    status: str
    recipe_path: str
    proof_band_path: str | None = None
    weights_hash: str
    dataset_hash: str
    eval_hash: str
    sample_count: int
    heldout_count: int
    correct_count: int
    wrong_count: int
    native_accuracy_ppm: int
    oracle_accuracy_ppm: int
    continuous_cycle_count: int
    cycle_receipt_count: int
    latest_cycle_seq: int | None = None
    training_source: str | None = None
    larger_heldout_window_pass: bool
    proof_status: str
    native_beats_oracle: bool
    observed_at: str | None = None
    receipt_path: str


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _short_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _receipt_string(record: dict[str, Any], key: str, fallback: str = "") -> str:
    value = record.get(key)
    return str(value).strip() if value is not None and str(value).strip() else fallback


def _receipt_int(record: dict[str, Any], key: str) -> int:
    value = record.get(key)
    return value if isinstance(value, int) else 0


def _receipt_hash(section: Any) -> str:
    if not isinstance(section, dict):
        return ""
    value = section.get("hash")
    return str(value).strip() if value is not None and str(value).strip() else ""


def _receipt_is_trained(record: dict[str, Any]) -> bool:
    weights = record.get("weights")
    data = record.get("data")
    eval_data = record.get("eval")
    validation = record.get("validation")
    closed_eval = (
        _receipt_int(eval_data, "correct_count") + _receipt_int(eval_data, "wrong_count")
        == _receipt_int(eval_data, "heldout_count")
    )
    return (
        _receipt_string(record, "status") == "active"
        and _receipt_int(record, "continuous_cycle_count") > 0
        and bool(_receipt_hash(weights))
        and bool(_receipt_hash(data))
        and bool(_receipt_hash(eval_data))
        and isinstance(data, dict)
        and isinstance(eval_data, dict)
        and _receipt_int(data, "sample_count") > 0
        and _receipt_int(eval_data, "heldout_count") > 0
        and closed_eval
        and isinstance(validation, dict)
        and _receipt_string(validation, "status") == "pass"
    )


def collect_native_training_artifacts(
    receipt_dir: Path,
    repo_root: Path,
    *,
    limit: int = 12,
) -> list[NativeTrainingArtifact]:
    artifacts: list[NativeTrainingArtifact] = []
    if not receipt_dir.exists():
        return artifacts
    for path in sorted(receipt_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        record = _load_json_file(path)
        if not record or not _receipt_is_trained(record):
            continue
        weights = record.get("weights") if isinstance(record.get("weights"), dict) else {}
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        eval_data = record.get("eval") if isinstance(record.get("eval"), dict) else {}
        training = record.get("training") if isinstance(record.get("training"), dict) else {}
        validation = record.get("validation") if isinstance(record.get("validation"), dict) else {}
        cycle_receipts = record.get("cycle_receipts") if isinstance(record.get("cycle_receipts"), list) else []
        latest_cycle = cycle_receipts[-1] if cycle_receipts and isinstance(cycle_receipts[-1], dict) else {}
        artifacts.append(
            NativeTrainingArtifact(
                artifact_id=_receipt_string(record, "artifact_id", path.stem),
                artifact_kind=_receipt_string(record, "artifact_kind", "native-training-artifact"),
                model_family=_receipt_string(record, "model_family", "Form-native"),
                status=_receipt_string(record, "status", "unknown"),
                recipe_path=_receipt_string(record, "recipe_path"),
                proof_band_path=_receipt_string(record, "proof_band_path") or None,
                weights_hash=_receipt_hash(weights),
                dataset_hash=_receipt_hash(data),
                eval_hash=_receipt_hash(eval_data),
                sample_count=_receipt_int(data, "sample_count"),
                heldout_count=_receipt_int(eval_data, "heldout_count"),
                correct_count=_receipt_int(eval_data, "correct_count"),
                wrong_count=_receipt_int(eval_data, "wrong_count"),
                native_accuracy_ppm=_receipt_int(eval_data, "native_accuracy_ppm"),
                oracle_accuracy_ppm=_receipt_int(eval_data, "oracle_accuracy_ppm"),
                continuous_cycle_count=_receipt_int(record, "continuous_cycle_count"),
                cycle_receipt_count=len(cycle_receipts),
                latest_cycle_seq=_receipt_int(latest_cycle, "seq") or None,
                training_source=_receipt_string(training, "source") or None,
                larger_heldout_window_pass=bool(training.get("larger_heldout_window_pass")),
                proof_status=_receipt_string(validation, "status", "unknown"),
                native_beats_oracle=bool(training.get("native_beats_oracle")),
                observed_at=_receipt_string(record, "observed_at") or None,
                receipt_path=_short_path(path, repo_root),
            )
        )
        if len(artifacts) >= limit:
            break
    return artifacts

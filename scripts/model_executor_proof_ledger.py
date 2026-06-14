#!/usr/bin/env python3
"""Validate and export native model executor proof-run records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "run_id",
    "thread_branch",
    "model_used",
    "input_tokens",
    "output_tokens",
    "attempts",
    "commands_run",
    "pass_fail",
    "failure_reason",
    "source",
    "validation",
}
LEGACY_FIELDS = (
    "model_used",
    "input_tokens",
    "output_tokens",
    "attempts",
    "commands_run",
    "pass_fail",
    "failure_reason",
)
VALID_PASS_FAIL = {"pass", "fail"}
DEFAULT_LEDGER_DIR = Path("docs/system_audit/model_executor_run_ledger")


class LedgerError(ValueError):
    """Raised when a native proof-run record is malformed."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LedgerError(f"{path}: cannot read file: {exc}") from exc
    except ValueError as exc:
        raise LedgerError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LedgerError(f"{path}: record must be a JSON object")
    return payload


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_non_empty_string(item) for item in value)


def validate_record(record: dict[str, Any], *, path: Path | None = None) -> list[str]:
    label = str(path) if path else str(record.get("run_id") or "<memory>")
    errors: list[str] = []

    missing = sorted(field for field in REQUIRED_FIELDS if field not in record)
    if missing:
        errors.append(f"{label}: missing required fields: {missing}")

    for field in ("run_id", "thread_branch", "model_used", "failure_reason"):
        if field in record and not _non_empty_string(record.get(field)):
            errors.append(f"{label}: {field} must be a non-empty string")

    for field in ("input_tokens", "output_tokens", "attempts"):
        value = record.get(field)
        if not isinstance(value, int) or value < 0:
            errors.append(f"{label}: {field} must be a non-negative integer")

    if record.get("attempts") == 0:
        errors.append(f"{label}: attempts must be at least 1")

    if "commands_run" in record and not _non_empty_string_list(record.get("commands_run")):
        errors.append(f"{label}: commands_run must be a non-empty list of strings")

    pass_fail = str(record.get("pass_fail") or "").strip().lower()
    if pass_fail not in VALID_PASS_FAIL:
        errors.append(f"{label}: pass_fail must be one of {sorted(VALID_PASS_FAIL)}")

    source = record.get("source")
    if not isinstance(source, dict):
        errors.append(f"{label}: source must be an object")
    else:
        if not _non_empty_string(source.get("kind")):
            errors.append(f"{label}: source.kind must be a non-empty string")
        if not _non_empty_string(source.get("path")):
            errors.append(f"{label}: source.path must be a non-empty string")

    validation = record.get("validation")
    if not isinstance(validation, dict):
        errors.append(f"{label}: validation must be an object")
    else:
        if str(validation.get("status") or "").strip().lower() not in {"pass", "fail", "pending"}:
            errors.append(f"{label}: validation.status must be pass, fail, or pending")
        if not _non_empty_string_list(validation.get("commands")):
            errors.append(f"{label}: validation.commands must be a non-empty list of strings")

    return errors


def load_records(ledger_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not ledger_dir.exists():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(ledger_dir.glob("*.json")):
        records.append((path, _load_json(path)))
    return records


def validate_ledger(ledger_dir: Path) -> list[str]:
    records = load_records(ledger_dir)
    errors: list[str] = []
    seen: dict[str, Path] = {}
    for path, record in records:
        errors.extend(validate_record(record, path=path))
        run_id = str(record.get("run_id") or "").strip()
        if not run_id:
            continue
        prior = seen.get(run_id)
        if prior is not None:
            errors.append(f"{path}: duplicate run_id {run_id!r}; first seen in {prior}")
        seen[run_id] = path
    return errors


def legacy_row(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record[field] for field in LEGACY_FIELDS}


def export_jsonl(ledger_dir: Path) -> str:
    rows = [legacy_row(record) for _path, record in load_records(ledger_dir)]
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or export native executor proof-run records")
    parser.add_argument(
        "command",
        choices=("validate", "export-jsonl"),
        help="validate native records or export them as legacy JSONL",
    )
    parser.add_argument(
        "--ledger-dir",
        type=Path,
        default=DEFAULT_LEDGER_DIR,
        help=f"Native ledger directory (default: {DEFAULT_LEDGER_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write export-jsonl output to this path instead of stdout",
    )
    args = parser.parse_args()

    errors = validate_ledger(args.ledger_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.command == "validate":
        print(f"OK: model executor proof ledger valid ({len(load_records(args.ledger_dir))} record(s))")
        return 0

    payload = export_jsonl(args.ledger_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"OK: wrote {args.output}")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

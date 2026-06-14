#!/usr/bin/env python3
"""Validate and export native model executor proof-run records."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
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
VALID_PASS_FAIL = {"pass", "fail", "pending"}
DEFAULT_LEDGER_DIR = Path("docs/system_audit/model_executor_run_ledger")
DEFAULT_LEGACY_JSONL = Path("docs/system_audit/model_executor_runs.jsonl")


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

    for field in ("run_id", "thread_branch", "model_used"):
        if field in record and not _non_empty_string(record.get(field)):
            errors.append(f"{label}: {field} must be a non-empty string")
    if "failure_reason" in record and not isinstance(record.get("failure_reason"), str):
        errors.append(f"{label}: failure_reason must be a string")

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


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _legacy_signature(row: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(row).encode("utf-8")).hexdigest()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "legacy-row"


def load_legacy_jsonl(jsonl_path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    if not jsonl_path.exists():
        return rows
    try:
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise LedgerError(f"{jsonl_path}: cannot read file: {exc}") from exc
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise LedgerError(f"{jsonl_path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise LedgerError(f"{jsonl_path}:{line_no}: row must be a JSON object")
        rows.append((line_no, row))
    return rows


def validate_legacy_row(row: dict[str, Any], *, label: str) -> list[str]:
    errors: list[str] = []
    missing = [field for field in LEGACY_FIELDS if field not in row]
    if missing:
        errors.append(f"{label}: missing legacy fields: {missing}")
        return errors
    record = {
        "run_id": label,
        "thread_branch": "legacy-jsonl-import",
        "source": {"kind": "legacy-jsonl-import", "path": label},
        "validation": {
            "status": str(row.get("pass_fail") or "pending").strip().lower(),
            "commands": row.get("commands_run"),
        },
        **{field: row[field] for field in LEGACY_FIELDS},
    }
    errors.extend(validate_record(record, path=Path(label)))
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
    return "".join(_canonical_json(row) + "\n" for row in rows)


def _projection_counter(records: list[tuple[Path, dict[str, Any]]]) -> Counter[str]:
    return Counter(_canonical_json(legacy_row(record)) for _path, record in records)


def import_jsonl(ledger_dir: Path, jsonl_path: Path) -> list[Path]:
    records = load_records(ledger_dir)
    available_native_counts = Counter(_legacy_signature(legacy_row(record)) for _path, record in records)
    written: list[Path] = []

    for line_no, row in load_legacy_jsonl(jsonl_path):
        label = f"{jsonl_path}:{line_no}"
        errors = validate_legacy_row(row, label=label)
        if errors:
            raise LedgerError("; ".join(errors))
        signature = _legacy_signature(row)
        if available_native_counts[signature] > 0:
            available_native_counts[signature] -= 1
            continue

        run_id = f"legacy-jsonl-{line_no:04d}-{signature[:12]}"
        path = ledger_dir / f"{run_id}.json"
        record = {
            "ledger_schema": "model_executor_proof_run/v1",
            "run_id": run_id,
            "thread_branch": "legacy-jsonl-import",
            "model_used": row["model_used"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "attempts": row["attempts"],
            "commands_run": row["commands_run"],
            "pass_fail": row["pass_fail"],
            "failure_reason": row["failure_reason"],
            "source": {
                "kind": "legacy-jsonl-import",
                "path": f"{jsonl_path}#L{line_no}",
            },
            "validation": {
                "status": str(row["pass_fail"]).strip().lower(),
                "commands": row["commands_run"],
            },
            "legacy": {
                "jsonl_path": str(jsonl_path),
                "line": line_no,
                "row_sha256": signature,
                "summary": _slug(str(row["failure_reason"])),
            },
        }
        errors = validate_record(record, path=path)
        if errors:
            raise LedgerError("; ".join(errors))
        ledger_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


def sync_jsonl(ledger_dir: Path, jsonl_path: Path) -> str:
    records = load_records(ledger_dir)
    remaining = _projection_counter(records)
    rows: list[dict[str, Any]] = []

    for _line_no, row in load_legacy_jsonl(jsonl_path):
        canonical = _canonical_json(row)
        if remaining[canonical] <= 0:
            continue
        rows.append(row)
        remaining[canonical] -= 1

    for _path, record in records:
        row = legacy_row(record)
        canonical = _canonical_json(row)
        if remaining[canonical] <= 0:
            continue
        rows.append(row)
        remaining[canonical] -= 1

    return "".join(_canonical_json(row) + "\n" for row in rows)


def check_jsonl(ledger_dir: Path, jsonl_path: Path) -> list[str]:
    errors: list[str] = []
    legacy_rows = load_legacy_jsonl(jsonl_path)
    for line_no, row in legacy_rows:
        errors.extend(validate_legacy_row(row, label=f"{jsonl_path}:{line_no}"))
    native = _projection_counter(load_records(ledger_dir))
    legacy = Counter(_canonical_json(row) for _line_no, row in legacy_rows)
    for canonical, count in sorted((native - legacy).items()):
        errors.append(f"{jsonl_path}: missing {count} native projection row(s): {canonical}")
    for canonical, count in sorted((legacy - native).items()):
        errors.append(f"{jsonl_path}: has {count} row(s) without native ledger record: {canonical}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or export native executor proof-run records")
    parser.add_argument(
        "command",
        choices=("validate", "export-jsonl", "import-jsonl", "sync-jsonl", "check-jsonl"),
        help="validate native records, import legacy JSONL, or sync/check the JSONL cache",
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
        help="Write export-jsonl or sync-jsonl output to this path instead of stdout",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=DEFAULT_LEGACY_JSONL,
        help=f"Legacy JSONL cache path (default: {DEFAULT_LEGACY_JSONL})",
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

    if args.command == "import-jsonl":
        try:
            written = import_jsonl(args.ledger_dir, args.jsonl)
        except LedgerError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"OK: imported {len(written)} legacy JSONL row(s) into {args.ledger_dir}")
        return 0

    if args.command == "check-jsonl":
        try:
            jsonl_errors = check_jsonl(args.ledger_dir, args.jsonl)
        except LedgerError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if jsonl_errors:
            for error in jsonl_errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"OK: {args.jsonl} matches native ledger projection")
        return 0

    payload = sync_jsonl(args.ledger_dir, args.jsonl) if args.command == "sync-jsonl" else export_jsonl(args.ledger_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"OK: wrote {args.output}")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

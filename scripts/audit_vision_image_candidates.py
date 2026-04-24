#!/usr/bin/env python3
"""Audit regenerated vision image candidates before production promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "visuals" / "prompts.json"
DEFAULT_CANDIDATE_DIR = REPO_ROOT / "output" / "vision-quality" / "candidates"
DEFAULT_REPORT = REPO_ROOT / "output" / "vision-quality" / "candidate-audit.json"
DEFAULT_MIN_BYTES = 8_000


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rel(path: Path) -> str:
    resolved = path if path.is_absolute() else REPO_ROOT / path
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _records_from_manifest(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"manifest has no records list: {_rel(path)}")
    return [record for record in records if isinstance(record, dict)]


def _records_from_batch(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"batch has no records list: {_rel(path)}")
    return [record for record in records if isinstance(record, dict)]


def _select_records(records: list[dict[str, Any]], only_path: str | None) -> list[dict[str, Any]]:
    if not only_path:
        return records
    selected: list[dict[str, Any]] = []
    for record in records:
        aliases = [
            str(record.get("id") or ""),
            str(record.get("path") or ""),
            *[str(path) for path in record.get("mirror_paths") or []],
        ]
        if only_path in aliases:
            selected.append(record)
    return selected


def _candidate_path(record: dict[str, Any], candidate_dir: Path) -> Path:
    base = candidate_dir if candidate_dir.is_absolute() else REPO_ROOT / candidate_dir
    return base / str(record.get("path") or "")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_dimensions(raw: bytes) -> tuple[int, int] | None:
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) < 24:
        return None
    width, height = struct.unpack(">II", raw[16:24])
    return int(width), int(height)


def _jpeg_dimensions(raw: bytes) -> tuple[int, int] | None:
    if raw[:2] != b"\xff\xd8":
        return None
    index = 2
    while index + 9 < len(raw):
        if raw[index] != 0xFF:
            index += 1
            continue
        marker = raw[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(raw):
            return None
        segment_length = int.from_bytes(raw[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(raw):
            return None
        if 0xC0 <= marker <= 0xC3 and segment_length >= 7:
            height = int.from_bytes(raw[index + 3 : index + 5], "big")
            width = int.from_bytes(raw[index + 5 : index + 7], "big")
            return width, height
        index += segment_length
    return None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    raw = path.read_bytes()
    return _png_dimensions(raw) or _jpeg_dimensions(raw)


def audit_records(
    records: list[dict[str, Any]],
    candidate_dir: Path,
    *,
    profile_id: str | None,
    min_bytes: int,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    missing = 0
    too_small = 0
    unreadable_dimensions = 0

    for record in records:
        candidate = _candidate_path(record, candidate_dir)
        item: dict[str, Any] = {
            "id": record.get("id"),
            "source_path": record.get("path"),
            "candidate_path": _rel(candidate),
            "profile": profile_id,
            "prompt_sha256": hashlib.sha256(
                str(record.get("prompt") or "").encode("utf-8")
            ).hexdigest(),
            "exists": candidate.exists(),
        }
        if not candidate.exists():
            missing += 1
            items.append(item)
            continue

        size_bytes = candidate.stat().st_size
        dims = image_dimensions(candidate)
        item["size_bytes"] = size_bytes
        item["sha256"] = _sha256(candidate)
        item["width"] = dims[0] if dims else None
        item["height"] = dims[1] if dims else None
        item["passes_min_bytes"] = size_bytes >= min_bytes
        item["passes_dimensions"] = dims is not None
        if size_bytes < min_bytes:
            too_small += 1
        if dims is None:
            unreadable_dimensions += 1
        items.append(item)

    fail_count = missing + too_small + unreadable_dimensions
    return {
        "schema_version": 1,
        "candidate_dir": _rel(candidate_dir),
        "profile": profile_id,
        "min_bytes": min_bytes,
        "summary": {
            "total": len(records),
            "present": len(records) - missing,
            "missing": missing,
            "too_small": too_small,
            "unreadable_dimensions": unreadable_dimensions,
            "pass": fail_count == 0,
        },
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit regenerated vision image candidates")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--batch-file", type=Path)
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATE_DIR)
    parser.add_argument("--only-path")
    parser.add_argument("--profile")
    parser.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    try:
        records = _records_from_batch(args.batch_file) if args.batch_file else _records_from_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    records = _select_records(records, args.only_path)
    if args.only_path and not records:
        print(f"No manifest record matched: {args.only_path}", file=sys.stderr)
        return 1

    report = audit_records(
        records,
        args.candidate_dir,
        profile_id=args.profile,
        min_bytes=args.min_bytes,
    )
    report_path = args.report if args.report.is_absolute() else REPO_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        "Vision candidate audit: "
        f"{summary['present']}/{summary['total']} present, "
        f"missing={summary['missing']}, too_small={summary['too_small']}, "
        f"unreadable_dimensions={summary['unreadable_dimensions']} -> {_rel(report_path)}"
    )
    if args.allow_missing and summary["missing"] and not summary["too_small"] and not summary["unreadable_dimensions"]:
        return 0
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

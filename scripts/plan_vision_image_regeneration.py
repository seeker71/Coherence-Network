#!/usr/bin/env python3
"""Split the vision prompt manifest into deterministic regeneration batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "visuals" / "prompts.json"
DEFAULT_OUT_DIR = REPO_ROOT / "output" / "vision-quality" / "batches"


def _rel(path: Path) -> str:
    resolved = path if path.is_absolute() else REPO_ROOT / path
    return str(resolved.relative_to(REPO_ROOT))


def load_records(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = manifest.get("records")
    if not isinstance(records, list):
        raise ValueError(f"manifest has no records list: {_rel(manifest_path)}")
    valid_records = [
        record for record in records
        if isinstance(record, dict) and record.get("path") and record.get("prompt")
    ]
    return sorted(valid_records, key=lambda record: str(record["path"]))


def write_batches(records: list[dict[str, Any]], out_dir: Path, batch_size: int) -> list[Path]:
    out_dir = out_dir if out_dir.is_absolute() else REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index in range(0, len(records), batch_size):
        batch = records[index:index + batch_size]
        batch_number = index // batch_size + 1
        path = out_dir / f"vision-image-batch-{batch_number:03d}.json"
        payload = {
            "schema_version": 1,
            "batch_number": batch_number,
            "batch_size": len(batch),
            "records": batch,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan deterministic vision image regeneration batches")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()

    if args.batch_size < 1:
        print("--batch-size must be >= 1")
        return 1

    records = load_records(args.manifest)
    written = write_batches(records, args.out_dir, args.batch_size)
    print(
        f"Planned {len(records)} vision images into {len(written)} batches "
        f"under {_rel(args.out_dir)}"
    )
    for path in written:
        print(f"  - {_rel(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

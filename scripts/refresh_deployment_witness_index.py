#!/usr/bin/env python3
"""Refresh only the recorded deployment WITNESS in the native RAG index.

The release path owns whole-body substrate/index reconciliation.  The public
observer runs after that release and adds exactly one dynamic WITNESS.  Keeping
this retiring host carrier witness-only prevents an independent verification
read from repeating a whole-body heal inside the serving API container.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import form_cli_rag as rag  # noqa: E402


def refresh(index_path: str) -> tuple[int, int]:
    """Atomically replace stale deployment witnesses with the current one."""
    if not rag._index_stamp_valid(index_path):
        raise RuntimeError(
            "deployment WITNESS refresh requires the release-healed base index"
        )

    witnesses = rag._deployment_witness_entries()
    if len(witnesses) != 1:
        raise RuntimeError(
            "deployment WITNESS refresh requires exactly one persisted witness"
        )

    # Native work is bounded to the single dynamic witness.  If embedding fails,
    # _write_index is never reached and the previously valid index stays intact.
    rag._attach_native_embeddings(witnesses)
    existing = rag._load_index(index_path)
    retained = [
        entry for entry in existing if entry.get("kind") != "deployment-witness"
    ]
    removed = len(existing) - len(retained)
    rag._write_index(index_path, retained + witnesses)
    return len(witnesses), removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default=rag.INDEX)
    args = parser.parse_args()
    added, removed = refresh(args.index)
    print(
        f"[deployment WITNESS refresh: +{added} current, "
        f"-{removed} stale -> {args.index}]"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"deployment WITNESS refresh: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

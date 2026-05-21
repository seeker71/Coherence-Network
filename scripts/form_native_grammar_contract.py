#!/usr/bin/env python3
"""Audit Form-native grammar status without counting host parser bridges as done."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GRAMMAR_DIR = REPO_ROOT / "docs" / "coherence-substrate"
FORM_CLI = REPO_ROOT / "scripts" / "form_cli.py"

EXTENSION_TO_GRAMMAR = {
    "json": "json-grammar.form",
    "jsonl": "json-grammar.form",
    "yaml": "yaml-grammar.form",
    "yml": "yaml-grammar.form",
    "md": "markdown-grammar.form",
    "py": "python-grammar.form",
    "rs": "rust-grammar.form",
    "go": "go-grammar.form",
    "png": "png-grammar.form",
    "jpg": "image-grammar.form",
    "jpeg": "image-grammar.form",
    "gif": "image-grammar.form",
    "svg": "image-grammar.form",
    "webp": "image-grammar.form",
    "mp3": "audio-grammar.form",
    "wav": "audio-grammar.form",
    "flac": "audio-grammar.form",
    "ogg": "audio-grammar.form",
    "m4a": "audio-grammar.form",
}

BINARY_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp", "mp3", "wav", "flac", "ogg", "m4a"
}

HOST_BRIDGE_PATTERNS = {
    "json": ["json.loads", "json.dumps"],
    "markdown": ["_HEADING_RE", "_md_parse_blocks", "_convert_in_markdown"],
    "python": ["import ast", "ast.parse", "ast.unparse", "_convert_in_python"],
}


def _repo_extensions() -> dict[str, int]:
    counts: dict[str, int] = {}
    skip_parts = {".git", "node_modules", ".claude", ".next", ".venv", "__pycache__", "dist", "build"}
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in skip_parts for part in rel_parts):
            continue
        ext = path.suffix.lstrip(".").lower()
        if ext:
            counts[ext] = counts.get(ext, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _existing_grammars() -> set[str]:
    return {path.name for path in GRAMMAR_DIR.glob("*-grammar.form")}


def _native_stream_cells() -> set[str]:
    cells: set[str] = set()
    if not FORM_CLI.exists():
        return cells
    text = FORM_CLI.read_text(encoding="utf-8")
    for match in re.finditer(r"if args\.tongue(?: in)? .*?\"([a-z]+)\"", text):
        cells.add(match.group(1))
    # The current CLI entries are host bridges, not native stream cells.
    return cells - set(HOST_BRIDGE_PATTERNS)


def _host_bridges() -> dict[str, list[str]]:
    if not FORM_CLI.exists():
        return {}
    text = FORM_CLI.read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    for tongue, patterns in HOST_BRIDGE_PATTERNS.items():
        hits = [pattern for pattern in patterns if pattern in text]
        if hits:
            found[tongue] = hits
    return found


def audit() -> dict[str, Any]:
    counts = _repo_extensions()
    existing = _existing_grammars()
    native_stream = _native_stream_cells()
    host_bridges = _host_bridges()
    rows = []
    for ext, count in counts.items():
        if count < 2:
            continue
        grammar = EXTENSION_TO_GRAMMAR.get(ext)
        grammar_declared = bool(grammar and grammar in existing)
        tongue = (grammar or "").replace("-grammar.form", "") if grammar else None
        rows.append({
            "extension": ext,
            "count": count,
            "grammar": grammar if grammar_declared else None,
            "grammar_declared": grammar_declared,
            "binary": ext in BINARY_EXTENSIONS,
            "form_native_stream": bool(tongue and tongue in native_stream),
            "host_bridge": tongue in host_bridges if tongue else False,
            "unmapped": ext not in EXTENSION_TO_GRAMMAR,
        })
    return {
        "contract": (
            "Complete means bytes stream through grammar authored in .form "
            "and emit Form-native cells; host parser bridges are debt."
        ),
        "grammar_files": sorted(existing),
        "host_bridges": host_bridges,
        "extensions": rows,
        "summary": {
            "declared_grammar_extensions": sum(1 for row in rows if row["grammar_declared"]),
            "form_native_stream_extensions": sum(1 for row in rows if row["form_native_stream"]),
            "host_bridge_tongues": sorted(host_bridges),
            "binary_declared_not_native": [
                row["extension"] for row in rows
                if row["binary"] and row["grammar_declared"] and not row["form_native_stream"]
            ],
            "missing_grammar_extensions": [
                row["extension"] for row in rows
                if not row["grammar_declared"]
            ],
        },
    }


def print_text(report: dict[str, Any]) -> None:
    print("Form-native grammar contract")
    print("=" * 36)
    print(report["contract"])
    print()
    summary = report["summary"]
    print(f"declared grammar extensions: {summary['declared_grammar_extensions']}")
    print(f"Form-native stream extensions: {summary['form_native_stream_extensions']}")
    print(f"host parser bridges: {', '.join(summary['host_bridge_tongues']) or 'none'}")
    print(
        "binary grammars declared but not native: "
        f"{', '.join(summary['binary_declared_not_native']) or 'none'}"
    )
    print()
    print("Top extension status:")
    for row in report["extensions"][:30]:
        if row["form_native_stream"]:
            status = "native-stream"
        elif row["host_bridge"]:
            status = "host-bridge"
        elif row["grammar_declared"]:
            status = "declared-only"
        elif row["unmapped"]:
            status = "unmapped"
        else:
            status = "missing-grammar"
        grammar = row["grammar"] or "-"
        print(f"  {row['extension']:<8} {row['count']:>5}  {grammar:<24} {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--fail-on-host-bridges",
        action="store_true",
        help="exit non-zero while any host parser bridge remains",
    )
    args = parser.parse_args()

    report = audit()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    if args.fail_on_host_bridges and report["host_bridges"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

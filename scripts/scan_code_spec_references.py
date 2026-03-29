#!/usr/bin/env python3
# spec: 181-full-code-traceability
# idea: full-code-traceability
"""Phase 1.3 — Scan code files for spec references and build spec_links report.

Scans all .py, .ts, .tsx files under api/ and web/ for comments/docstrings
matching spec:, spec_id:, # spec NNN, or SPEC-NNN patterns.

Outputs:
  - Console report with per-module coverage
  - data/spec_links.csv with (source_file, line_number, spec_id, function_name, confidence)

Usage:
    python3 scripts/scan_code_spec_references.py
    python3 scripts/scan_code_spec_references.py --module routers
    python3 scripts/scan_code_spec_references.py --format csv
"""

from __future__ import annotations

import argparse
import ast
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api" / "app"
WEB_DIR = REPO_ROOT / "web" / "app"
DATA_DIR = REPO_ROOT / "data"

_SPEC_PATTERNS = [
    re.compile(r"#\s*spec:\s*(\S+)", re.IGNORECASE),
    re.compile(r"#\s*Implements:\s*spec[_-]?(\S+)", re.IGNORECASE),
    re.compile(r"//\s*spec:\s*(\S+)", re.IGNORECASE),
    re.compile(r"//\s*Implements:\s*spec[_-]?(\S+)", re.IGNORECASE),
    re.compile(r'"""[^"]*[Ss]pec[_:\s]+(\d{2,3})', re.DOTALL),
    re.compile(r"Spec[:\s]+(\d{2,3})\b"),
    re.compile(r"spec[_-](\d{2,3})\b", re.IGNORECASE),
]


def _extract_spec_refs_from_line(line: str) -> list[tuple[str, float]]:
    """Find spec references in a single line. Returns list of (spec_id, confidence)."""
    refs = []
    for pattern in _SPEC_PATTERNS[:4]:  # High-confidence: explicit comment patterns
        m = pattern.search(line)
        if m:
            refs.append((m.group(1).strip(), 1.0))
    for pattern in _SPEC_PATTERNS[4:]:  # Lower confidence: body mentions
        m = pattern.search(line)
        if m:
            spec_ref = m.group(1).strip()
            if not any(r[0] == spec_ref for r in refs):
                refs.append((spec_ref, 0.7))
    return refs


def _current_function_at_line(source_lines: list[str], line_num: int) -> str | None:
    """Find the enclosing function name for a given line number (1-indexed)."""
    for i in range(line_num - 1, -1, -1):
        line = source_lines[i]
        m = re.match(r"^\s{0,8}(?:async )?def (\w+)\s*\(", line)
        if m:
            return m.group(1)
    return None


def scan_file(file_path: Path) -> list[dict]:
    """Scan a single file for spec references. Returns list of link entries."""
    links = []
    try:
        content = file_path.read_text(errors="replace")
    except OSError:
        return links

    lines = content.splitlines()
    seen: set[tuple[str, str]] = set()  # (spec_id, function_name)

    for i, line in enumerate(lines, start=1):
        refs = _extract_spec_refs_from_line(line)
        for spec_id, confidence in refs:
            fn_name = _current_function_at_line(lines, i) or ""
            key = (spec_id, fn_name)
            if key in seen:
                continue
            seen.add(key)
            try:
                rel_path = str(file_path.relative_to(REPO_ROOT))
            except ValueError:
                rel_path = str(file_path)
            links.append({
                "source_file": rel_path,
                "line_number": i,
                "spec_id": spec_id,
                "function_name": fn_name or None,
                "confidence": confidence,
            })
    return links


def scan_directory(base_dir: Path, extensions: tuple[str, ...] = (".py", ".ts", ".tsx"),
                   module_filter: str | None = None) -> tuple[list[dict], int]:
    """Scan a directory for spec references. Returns (links, total_files_scanned)."""
    all_links: list[dict] = []
    total = 0

    if not base_dir.exists():
        return all_links, total

    for ext in extensions:
        for f in sorted(base_dir.rglob(f"*{ext}")):
            if "__pycache__" in str(f) or "node_modules" in str(f):
                continue
            if f.name.startswith("test_"):
                continue
            if module_filter and module_filter not in str(f):
                continue
            total += 1
            links = scan_file(f)
            all_links.extend(links)

    return all_links, total


def coverage_by_module(links: list[dict], total_by_module: dict[str, int]) -> dict[str, dict]:
    """Compute per-module coverage."""
    module_files: dict[str, set[str]] = defaultdict(set)
    for link in links:
        src = link["source_file"]
        parts = Path(src).parts
        # Use first meaningful subdirectory under api/app/ or web/app/
        for i, part in enumerate(parts):
            if part in ("routers", "services", "models", "middleware", "core", "utils", "adapters"):
                module_files[part].add(src)
                break
        else:
            module_files["other"].add(src)

    result = {}
    for module, files in sorted(module_files.items()):
        total = total_by_module.get(module, 1)
        result[module] = {
            "files_with_refs": len(files),
            "total_files": total,
            "coverage_pct": round(len(files) * 100.0 / max(total, 1), 1),
            "spec_refs": sorted({
                link["spec_id"]
                for link in links
                if Path(link["source_file"]).parts
                and any(p == module for p in Path(link["source_file"]).parts)
            }),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan code files for spec references")
    parser.add_argument("--module", help="Filter to a specific module directory (e.g. routers)")
    parser.add_argument("--format", choices=["text", "csv"], default="text")
    args = parser.parse_args()

    DATA_DIR.mkdir(exist_ok=True)

    print("Scanning code for spec references...")
    api_links, api_total = scan_directory(API_DIR, module_filter=args.module)
    web_links, web_total = scan_directory(WEB_DIR, module_filter=args.module)
    all_links = api_links + web_links
    total_files = api_total + web_total

    files_with_refs = len({link["source_file"] for link in all_links})
    coverage_pct = round(files_with_refs * 100.0 / max(total_files, 1), 1)

    if args.format == "csv":
        out_path = DATA_DIR / "spec_links.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["source_file", "line_number", "spec_id", "function_name", "confidence"]
            )
            writer.writeheader()
            writer.writerows(all_links)
        print(f"Written {len(all_links)} links to {out_path}")
    else:
        print(f"\n=== Code Spec Reference Scan ===")
        print(f"Total files scanned:    {total_files}")
        print(f"Files with spec refs:   {files_with_refs} ({coverage_pct}%)")
        print(f"Total spec link entries:{len(all_links)}")
        unique_specs = sorted({link["spec_id"] for link in all_links})
        print(f"Unique specs referenced:{len(unique_specs)}")

        if all_links:
            print(f"\nSample links:")
            for link in all_links[:20]:
                fn = link["function_name"] or "-"
                print(f"  {link['source_file'][:45]:47s} line {link['line_number']:4d}  spec:{link['spec_id']:<30s} fn:{fn}")
            if len(all_links) > 20:
                print(f"  ... and {len(all_links) - 20} more")

        # Also write CSV always
        out_path = DATA_DIR / "spec_links.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["source_file", "line_number", "spec_id", "function_name", "confidence"]
            )
            writer.writeheader()
            writer.writerows(all_links)
        print(f"\nFull report: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

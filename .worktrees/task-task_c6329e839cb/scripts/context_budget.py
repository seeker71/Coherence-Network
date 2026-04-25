#!/usr/bin/env python3
"""Context-budget helper for large-file-aware code exploration.

This script helps the agent quickly choose what to open by reporting file sizes,
rough token costs, and cached, compact summaries before full-file reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT
CACHE_DIR = PROJECT_ROOT / ".cache" / "context_budget"
CACHE_FILE = CACHE_DIR / "summary_cache.json"
DEFAULT_TOKEN_BUDGET = 50000
SUMMARY_FILE_LINES = 12
SUMMARY_TOKEN_LIMIT = 1800
TOKENS_PER_BYTE = 0.25
TOKENS_PER_LINE = 2.0


@dataclass
class FileRecord:
    path: str
    size_bytes: int
    line_count: int
    sha256: str
    modified_at: float
    readable: bool = True
    summary: str = ""
    summary_version: str = "1"
    summary_generated_at: str | None = None
    token_estimate: int = field(init=False)

    def __post_init__(self) -> None:
        self.token_estimate = int((self.size_bytes * TOKENS_PER_BYTE) + (self.line_count * TOKENS_PER_LINE))



def _iter_input_files(paths: list[str]) -> list[Path]:
    candidates: list[Path] = []
    for raw in paths:
        has_wildcard = any(ch in raw for ch in "*?[")
        path = Path(raw).expanduser()
        if has_wildcard and not path.is_absolute():
            matches = list(PROJECT_ROOT.glob(raw))
            if not matches:
                matches = list(PROJECT_ROOT.rglob(raw))
            for match in matches:
                if match.is_file():
                    candidates.append(match.resolve())
                elif match.is_dir():
                    candidates.extend(_expand_one(match))
            continue

        resolved = path if path.is_absolute() else (PROJECT_ROOT / path).resolve()
        if resolved.is_dir():
            candidates.extend(_expand_one(resolved))
        elif resolved.is_file():
            candidates.append(resolved)
        else:
            raise FileNotFoundError(f"Path not found: {raw}")
    deduped = []
    seen: set[str] = set()
    for p in candidates:
        resolved = str(p.resolve())
        if resolved not in seen:
            deduped.append(p.resolve())
            seen.add(resolved)
    return deduped


def _expand_one(path: Path) -> list[Path]:
    if path.is_file():
        return [path.resolve()]
    if not path.exists() or not path.is_dir():
        return []
    out: list[Path] = []
    for entry in path.rglob("*"):
        if not entry.is_file():
            continue
        if _should_skip_path(entry):
            continue
        out.append(entry.resolve())
    return out


def _should_skip_path(path: Path) -> bool:
    lower = str(path).lower()
    skip_dirs = {
        "/.git/",
        "/.pytest_cache/",
        "/.cache/",
        "/__pycache__/",
        "/node_modules/",
        "/.next/",
        "/dist/",
        "/build/",
        "/vendor/",
        "/.mypy_cache/",
    }
    if any(part in lower for part in skip_dirs):
        return True
    suffix = path.suffix.lower()
    if suffix in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".mp4",
        ".mov",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".bz2",
        ".xz",
        ".bin",
        ".exe",
        ".pyc",
        ".pyo",
    }:
        return True
    return False


def _is_text_file(path: Path, sample_size: int = 4096) -> bool:
    try:
        with path.open("rb") as handle:
            sample = handle.read(sample_size)
        return b"\x00" not in sample
    except Exception:
        return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _line_count(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for _ in handle:
            count += 1
    return count


def _extract_summary(path: Path, max_lines: int = SUMMARY_FILE_LINES) -> str:
    if path.suffix.lower() in {".md", ".markdown", ".txt", ".rst"}:
        return _summary_text(path, max_lines=max_lines)
    if path.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}:
        return _summary_text(path, max_lines=max_lines)
    if path.suffix.lower() in {".py", ".pyi"}:
        return _summary_python(path)
    if path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}:
        return _summary_js(path)
    if path.suffix.lower() in {".sql"}:
        return _summary_text(path, max_lines=max_lines)
    return _summary_generic(path, max_lines=max_lines)


def _summary_text(path: Path, max_lines: int = SUMMARY_FILE_LINES) -> str:
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for idx, line in enumerate(handle):
            if idx >= max_lines:
                break
            lines.append(line.rstrip())
    if not lines:
        return "empty file"
    return "\n".join(lines)


def _summary_python(path: Path) -> str:
    symbols: list[str] = []
    pattern = re.compile(r"^\s*(async\s+)?def\s+([A-Za-z_][A-Za-z0-9_]*)|^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)")
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = pattern.match(line)
            if not m:
                continue
            if m.group(2):
                symbols.append(f"def {m.group(2)}")
            elif m.group(3):
                symbols.append(f"class {m.group(3)}")
            if len(symbols) >= SUMMARY_FILE_LINES:
                break
    return "symbols: " + ", ".join(symbols) if symbols else _summary_text(path, max_lines=SUMMARY_FILE_LINES)


def _summary_js(path: Path) -> str:
    symbols: list[str] = []
    pattern = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:function|const|class)\s+([A-Za-z_][A-Za-z0-9_]*)"
    )
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            m = pattern.match(line)
            if not m:
                continue
            symbols.append(m.group(0).strip())
            if len(symbols) >= SUMMARY_FILE_LINES:
                break
    return "symbols: " + ", ".join(symbols) if symbols else _summary_text(path, max_lines=SUMMARY_FILE_LINES)


def _summary_generic(path: Path, max_lines: int = SUMMARY_FILE_LINES) -> str:
    return _summary_text(path, max_lines=max_lines)


def _load_cache() -> dict[str, dict[str, Any]]:
    if not CACHE_FILE.exists():
        return {}
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _write_cache(entries: dict[str, dict[str, Any]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with CACHE_FILE.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=2)


def _cache_entry_key(record: FileRecord) -> str:
    return record.path


def inspect_files(
    paths: list[str],
    *,
    token_budget: int,
    force_summary: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    files = _iter_input_files(paths)
    cache = _load_cache()
    out: list[dict[str, Any]] = []
    budget_ok = True
    total_tokens = 0

    for file_path in sorted(files, key=lambda p: str(p).lower()):
        if not file_path.exists() or not file_path.is_file():
            continue
        if _should_skip_path(file_path):
            continue
        size = file_path.stat().st_size
        mtime = file_path.stat().st_mtime
        sha = _sha256_file(file_path) if size < 8_000_000 else "too_large_to_hash"
        is_readable = _is_text_file(file_path)
        line_count = _line_count(file_path) if is_readable else 0
        record = FileRecord(
            path=str(file_path),
            size_bytes=size,
            line_count=line_count,
            sha256=sha,
            modified_at=mtime,
            readable=is_readable,
        )
        record_dict: dict[str, Any] = asdict(record)
        cached = cache.get(_cache_entry_key(record))
        need_summary = force_summary or not cached
        if not need_summary and isinstance(cached, dict):
            if str(cached.get("sha256", "")) == sha and float(cached.get("modified_at", 0.0)) == mtime:
                cached_summary = str(cached.get("summary", ""))
                if cached_summary:
                    record.summary = cached_summary
                    record.summary_generated_at = str(cached.get("summary_generated_at", ""))

        if record.readable and (force_summary or not cached or str(cached.get("sha256", "")) != sha or float(cached.get("modified_at", 0.0)) != mtime):
            if size <= 1_000_000:
                record.summary = _extract_summary(file_path)
            else:
                record.summary = f"large_file_readable_size={size} bytes; summary skipped to preserve budget"
            record.summary_generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
            cache[_cache_entry_key(record)] = asdict(record)
        elif cached is not None and record.summary == "":
            record.summary = "cached_summary_unavailable"
        out.append(asdict(record))
        total_tokens += record.token_estimate

    # include text-only summaries for files we skipped from cache refresh for non-existent etc not needed
    for item in out:
        readable = bool(item.get("readable"))
        if readable and item.get("summary"):
            if isinstance(item.get("summary"), str):
                token_estimate = len(item["summary"]) // 4
                if token_estimate > SUMMARY_TOKEN_LIMIT:
                    item["summary"] = item["summary"][: SUMMARY_TOKEN_LIMIT * 4]
        if item["token_estimate"] > token_budget:
            budget_ok = False
        item["within_budget"] = item["token_estimate"] <= token_budget

    _write_cache(cache)
    return out, total_tokens <= token_budget and budget_ok


def _emit_console(records: list[dict[str, Any]], token_budget: int, total_tokens: int, within_budget: bool) -> None:
    print("Context budget plan")
    print(f"- files: {len(records)}")
    print(f"- token budget: {token_budget}")
    print(f"- estimated tokens (full reads): {total_tokens}")
    print(f"- within budget: {within_budget}")
    if not within_budget:
        print("- warning: one or more files exceed single-file budget estimate")

    records = sorted(records, key=lambda r: r["size_bytes"], reverse=True)
    for record in records:
        path = record["path"]
        size = int(record["size_bytes"])
        lines = int(record["line_count"])
        tokens = int(record["token_estimate"])
        readable = bool(record["readable"])
        budget_status = "ok" if record["within_budget"] else "large"
        print(f"- {path}")
        print(f"  bytes={size}, lines={lines}, est_tokens={tokens}, {budget_status}, readable={readable}")
        if record.get("summary"):
            print(f"  summary: {record['summary'][:120].replace(chr(10), ' | ')}")
        print(f"  summary_cached: {bool(record.get('summary_generated_at'))}")


def _emit_json(records: list[dict[str, Any]], token_budget: int, total_tokens: int, within_budget: bool) -> None:
    payload = {
        "token_budget": token_budget,
        "estimated_total_tokens": total_tokens,
        "within_budget": within_budget,
        "file_count": len(records),
        "files": records,
    }
    print(json.dumps(payload, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Context-aware file exploration helper.")
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files, directories, or glob patterns to inspect.",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=DEFAULT_TOKEN_BUDGET,
        help=f"Estimated token budget to compare against (default {DEFAULT_TOKEN_BUDGET}).",
    )
    parser.add_argument(
        "--force-summaries",
        action="store_true",
        help="Regenerate summaries even when cache is valid.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        records, within_budget = inspect_files(
            args.paths,
            token_budget=args.token_budget,
            force_summary=args.force_summaries,
        )
        total_tokens = sum(int(r["token_estimate"]) for r in records)
        if args.json:
            _emit_json(records, args.token_budget, total_tokens, within_budget)
        else:
            _emit_console(records, args.token_budget, total_tokens, within_budget)
        return 0 if within_budget else 3
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

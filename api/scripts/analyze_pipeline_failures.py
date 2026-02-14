#!/usr/bin/env python3
"""Summarize task failure patterns from metrics and task logs."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
METRICS_FILE = LOG_DIR / "metrics.jsonl"

ERROR_PATTERNS = [
    (re.compile(r"command not found", re.I), "command_not_found"),
    (re.compile(r"connection refused|api not reachable", re.I), "api_unreachable"),
    (re.compile(r"timeout|timed out", re.I), "timeout"),
    (re.compile(r"traceback|exception|error", re.I), "runtime_error"),
    (re.compile(r"422|validation", re.I), "validation_error"),
    (re.compile(r"permission|forbidden|unauthorized", re.I), "auth_or_permissions"),
]


def classify_line(line: str) -> str:
    s = (line or "").strip()
    if not s:
        return "empty_output"
    for pattern, label in ERROR_PATTERNS:
        if pattern.search(s):
            return label
    return "other_failure"


def _normalize_line(line: str) -> str:
    s = line.strip().lower()
    s = re.sub(r"task_[0-9a-f]{16}", "task_<id>", s)
    s = re.sub(r"\d+", "<n>", s)
    return s[:140]


def last_signal(task_id: str) -> tuple[str, str]:
    path = LOG_DIR / f"task_{task_id}.log"
    if not path.is_file():
        return "log_missing", "log_missing"
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    if not lines:
        return "log_empty", "log_empty"

    # Prefer the most specific error-like line in the tail window.
    tail = lines[-50:]
    for line in reversed(tail):
        label = classify_line(line)
        if label not in ("other_failure", "empty_output"):
            return label, _normalize_line(line)

    last = lines[-1]
    return classify_line(last), _normalize_line(last)


def main() -> None:
    if not METRICS_FILE.is_file():
        print(json.dumps({"error": "metrics file not found", "path": str(METRICS_FILE)}, indent=2))
        return

    records = []
    for line in METRICS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    status_counts = Counter(r.get("status", "unknown") for r in records)
    by_type = defaultdict(Counter)
    for r in records:
        by_type[r.get("task_type", "unknown")][r.get("status", "unknown")] += 1

    failed = [r for r in records if r.get("status") == "failed"]
    failure_signals = Counter()
    failure_examples = Counter()
    for rec in failed:
        task_id = rec.get("task_id", "")
        if not task_id:
            continue
        signal, example = last_signal(task_id)
        failure_signals[signal] += 1
        failure_examples[example] += 1

    completed = status_counts.get("completed", 0)
    failures = status_counts.get("failed", 0)
    total = completed + failures
    success_rate = round((completed / total), 3) if total else 0.0

    result = {
        "records": len(records),
        "status_counts": dict(status_counts),
        "success_rate": success_rate,
        "by_task_type": {k: dict(v) for k, v in by_type.items()},
        "failure_signals_top": failure_signals.most_common(10),
        "failure_examples_top": failure_examples.most_common(15),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

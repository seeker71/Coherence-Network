#!/usr/bin/env python3
"""Validate that workflow run-script file references exist in the repo."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"


@dataclass
class MissingRef:
    workflow: str
    line: int
    kind: str
    reference: str


_RX_COMMANDS: list[tuple[str, re.Pattern[str]]] = [
    ("pip_requirements", re.compile(r"\bpip(?:3)?\s+install\s+-r\s+([^\s\\]+)")),
    ("python_script", re.compile(r"\bpython(?:3)?\s+([^\s\\]+\.py)\b")),
    ("shell_script", re.compile(r"\b(?:bash|sh)\s+([^\s\\]+\.sh)\b")),
    ("exec_script", re.compile(r"(^|\s)(\./[^\s\\]+\.sh)\b")),
]

# A step's `cd <dir>` changes the working directory a relative reference resolves
# against (e.g. `cd form` then `./build-form-cli.sh` means `form/build-form-cli.sh`).
# Track it within a run block so cd-relative references are not false-flagged.
_RX_CD = re.compile(r"^\s*cd\s+([^\s&|;]+)")
_RX_STEP_BOUNDARY = re.compile(r"^\s*-\s|^\s*run:\s*[|>]?\s*$|^\s*run:\s")


def _normalize(token: str) -> str:
    out = token.strip().strip("\"'").strip()
    return out.rstrip("\\").strip()


def _is_dynamic(token: str) -> bool:
    return "$" in token or "${{" in token or token.startswith("http://") or token.startswith("https://")


def _collect_missing() -> tuple[list[MissingRef], int]:
    missing: list[MissingRef] = []
    checked = 0
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        try:
            lines = workflow.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        cwd = ""  # working dir (relative to ROOT) set by `cd` within the current run block
        for lineno, line in enumerate(lines, start=1):
            if _RX_STEP_BOUNDARY.match(line):
                cwd = ""  # a new step / run block resets the cd context
            cd_match = _RX_CD.match(line)
            if cd_match:
                target = _normalize(cd_match.group(1))
                if target and not target.startswith(("/", "~")) and not _is_dynamic(target):
                    cwd = target if not cwd else f"{cwd}/{target}"
            for kind, rx in _RX_COMMANDS:
                for match in rx.finditer(line):
                    raw = match.group(2) if kind == "exec_script" else match.group(1)
                    token = _normalize(raw)
                    if not token or _is_dynamic(token):
                        continue
                    checked += 1
                    candidate_paths = [
                        (ROOT / token).resolve(),
                        (ROOT / "api" / token).resolve(),
                    ]
                    if cwd:
                        candidate_paths.append((ROOT / cwd / token).resolve())
                    if not any(path.exists() for path in candidate_paths):
                        missing.append(
                            MissingRef(
                                workflow=str(workflow.relative_to(ROOT)),
                                line=lineno,
                                kind=kind,
                                reference=token,
                            )
                        )
    return missing, checked


def main() -> int:
    missing, checked = _collect_missing()
    payload = {
        "checked_references": checked,
        "missing_count": len(missing),
        "missing": [
            {
                "workflow": row.workflow,
                "line": row.line,
                "kind": row.kind,
                "reference": row.reference,
            }
            for row in missing
        ],
    }
    print(json.dumps(payload, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

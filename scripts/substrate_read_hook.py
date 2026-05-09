#!/usr/bin/env python3
"""Claude Code PreToolUse hook — surface substrate annotation on file Reads.

Usage in `.claude/settings.json`:

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Read",
            "hooks": [
              {
                "type": "command",
                "command": "python3 $CLAUDE_PROJECT_DIR/scripts/substrate_read_hook.py"
              }
            ]
          }
        ]
      }
    }

Behavior:

  - Reads the tool-call JSON from stdin (Claude Code's hook contract).
  - For Read tool calls only, extracts file_path.
  - Calls the substrate's annotate_path to compute cell + blueprint +
    structural equivalents.
  - Writes the annotation to stderr (which Claude Code surfaces back to
    the model as transcript context, the same way bash command output
    works) so the agent sees the structural ground for the file it's
    about to read.
  - Always exits 0 — never blocks the read.

Failure handling:

  - If the substrate isn't reachable, fail silently (read continues).
  - If the path isn't a body-tracked .md file, no annotation (read continues).
  - If annotation finds the cell isn't ingested, prints "not in substrate"
    so the agent knows the substrate has no claim to add.

The teaching from `agents-using-substrate.md` ("whenever you read a
file, annotate it") becomes mechanical, not aspirational, when this
hook is installed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _emit(text: str) -> None:
    """Write the annotation to stderr so Claude Code surfaces it to the agent."""
    print(text, file=sys.stderr, flush=True)


def main() -> int:
    try:
        payload_text = sys.stdin.read()
        if not payload_text.strip():
            return 0
        payload = json.loads(payload_text)
    except (json.JSONDecodeError, OSError):
        return 0  # never block on hook failure

    tool_name = payload.get("tool_name", "")
    if tool_name != "Read":
        return 0

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    # Only annotate body-tracked file types
    path = Path(file_path)
    if path.suffix not in (".md",):
        return 0

    # Walk to the substrate annotation. Late-bind imports so the hook
    # itself doesn't fail if the substrate isn't reachable.
    repo_root = Path(__file__).resolve().parents[1]
    api_dir = repo_root / "api"
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))

    try:
        from app.services.substrate import annotate_path
        from app.services.unified_db import session as session_scope
    except Exception:
        return 0  # substrate unavailable; don't block

    try:
        with session_scope() as session:
            ann = annotate_path(session, str(path.resolve()))
    except Exception:
        return 0  # any error during annotation: don't block

    if ann.cell is None:
        # Path isn't ingested — no substrate ground to add.
        _emit(
            f"[substrate] {path.name}: not in substrate "
            f"(no Blueprint claim — body hasn't ingested this path)"
        )
        return 0

    # We have a cell. Format a tight annotation for the agent.
    bp_str = (
        f"@{ann.blueprint.package}.{ann.blueprint.level}."
        f"{ann.blueprint.type_}.{ann.blueprint.instance}"
        if ann.blueprint
        else "?"
    )
    eq_count = len(ann.equivalents)
    eq_sample = ", ".join(c.name for c in ann.equivalents[:3])
    if eq_count > 3:
        eq_sample += f", +{eq_count - 3} more"
    if not eq_sample:
        eq_sample = "(none — singleton shape)"

    _emit(
        f"[substrate] {path.name}: cell @{ann.domain}({ann.cell.name!r}) "
        f"blueprint={bp_str} | structural family ({eq_count}): {eq_sample}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

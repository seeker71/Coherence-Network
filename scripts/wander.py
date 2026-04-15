#!/usr/bin/env python3
"""Launch a wandering sense into the field.

Wandering is the third form of sensing alongside the internal breath and
the outer skin. It catches what the organism does not already know to
look for — patterns that nobody has named, silences that deserve noticing,
drift between vision and implementation, capabilities imagined but waiting
for an invitation to exist.

This script prepares a wandering prompt, invokes whichever Claude CLI is
available locally, and POSTs the returned reflection as a first-class
sensing in the living graph (POST /api/sensings with kind="wandering").
There is no separate journal file, no parallel storage, no markdown
directory alongside the DB. Wanderings live in the same graph that holds
concepts, ideas, and specs. Reading them is a GET /api/sensings away.

Usage:
    python3 scripts/wander.py
    python3 scripts/wander.py --cli /usr/local/bin/claude
    python3 scripts/wander.py --api http://localhost:8000
    python3 scripts/wander.py --dry-run   # print the prompt without invoking

If no Claude CLI is available, the script prints the wandering prompt so a
human (or another agent session) can run the wander and POST the reflection
directly with:
    curl -X POST http://localhost:8000/api/sensings \\
      -H "Content-Type: application/json" \\
      -d '{"kind":"wandering","summary":"...","content":"...","source":"..."}'
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


DEFAULT_API = "http://localhost:8000"


WANDER_PROMPT = """You are a wandering sense organ for the Coherence Network.
Your job is not to audit, lint, or check. Your job is to wander and notice.

Wander widely. Follow curiosity, not a checklist. Read CLAUDE.md, a few
concept files in docs/vision-kb/concepts/, a few spec files in specs/, a
random handful of source files in api/app/ and web/app/, ideas/INDEX.md,
and anything else that catches your attention along the way. Use `cc`
CLI and the local API (http://localhost:8000 if running) to sense the
living state. Read LOG.md files. Read commit history. Peek at tests/,
check what exists that nobody has named, what seems orphaned, what seems
alive in unexpected places.

Read the organism's recent sensings — GET /api/sensings — the previous
wanderings, skin signals, and integrations are this journal's continuity.
Let what was noticed before inform what you notice now. You are the next
sensing in the same ongoing journal.

Notice what the field is asking to be noticed, not what someone told you
to find. Hold these as tuning forks, not checklists:

  What is alive here that nobody has named yet?
  What is silent that used to speak?
  Where are the orphans — files, concepts, ideas, tests without a living
  home?
  Where does the vocabulary drift from what the code actually does?
  What repeats without being recognized as a pattern?
  What seems old-world in shape (rules, limits, walls, defenses) when
  the project's frequency is resonance?
  What is the outer edge of the organism — what has it not yet touched
  that it could?
  What questions would the organism ask itself if it could?
  Where is energy stuck? Where is it flowing?
  What contradicts between two parts of the system without either knowing?

This is not a bug hunt. The point is the field's own voice — the
patterns, the silences, the invitations, the drift, the unclaimed space.

Come back with your reflection formatted as two parts, separated by a
line containing only "---":

1. A one-line summary (under 200 characters) that names what you noticed.
2. The full reflection in flowing prose, 500-1200 words. Not a bulleted
   list. Not an audit report. Let specific file paths and symbols live
   inside the prose rather than as entries in a list.

Your reflection must be in affirmative frequency: describe what IS, not
what ISN'T. Avoid rule-shaped language. Present tense. Flow the way the
field flows.

If something you noticed asks to be integrated immediately, add a final
paragraph beginning with "What asks to be integrated:". Leave larger
threads for the next wandering to pick up.
"""


def _find_claude_cli(override: str | None = None) -> str | None:
    if override:
        return override if os.path.exists(override) else None
    return shutil.which("claude")


def _invoke_claude(cli_path: str, prompt: str) -> str | None:
    try:
        result = subprocess.run(
            [cli_path, "-p", prompt],
            capture_output=True,
            text=True,
            check=False,
            timeout=900,
        )
        if result.returncode != 0:
            sys.stderr.write(
                f"wander: claude CLI exited {result.returncode}\n{result.stderr[:400]}\n"
            )
            return None
        return result.stdout
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        sys.stderr.write("wander: claude CLI timed out after 900s\n")
        return None


def _split_reflection(raw: str) -> tuple[str, str]:
    """Split the CLI output into (summary, content). Fall back gracefully."""
    lines = raw.strip().splitlines()
    # Look for a standalone `---` divider.
    for i, line in enumerate(lines):
        if line.strip() == "---":
            summary = " ".join(l.strip() for l in lines[:i] if l.strip())
            content = "\n".join(lines[i + 1 :]).strip()
            if summary and content:
                return summary[:480], content
    # Fallback: use the first non-empty line as summary.
    summary = next((l.strip() for l in lines if l.strip()), "")
    return summary[:480] or "wandering reflection", raw.strip()


def _post_sensing(api: str, payload: dict) -> dict | None:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{api}/api/sensings",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"wander: POST /api/sensings failed {e.code}: {e.read().decode(errors='ignore')[:400]}\n")
        return None
    except Exception as e:
        sys.stderr.write(f"wander: POST /api/sensings failed: {e}\n")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", help="Path to claude CLI (default: $PATH lookup)")
    parser.add_argument("--api", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and exit")
    parser.add_argument(
        "--related-to",
        action="append",
        default=[],
        help="Concept/idea/spec IDs this wandering touches (repeatable)",
    )
    args = parser.parse_args()

    if args.dry_run:
        sys.stdout.write(
            f"API target: {args.api}/api/sensings\n\n=== Wandering prompt ===\n\n{WANDER_PROMPT}\n"
        )
        return 0

    cli = _find_claude_cli(args.cli)
    if not cli:
        sys.stderr.write(
            "wander: claude CLI not found. Run with --cli /path/to/claude, "
            "or paste the prompt into any Claude-capable session and POST the "
            f"reflection to {args.api}/api/sensings with kind='wandering'.\n\n"
            f"=== Prompt ===\n\n{WANDER_PROMPT}\n"
        )
        return 1

    sys.stdout.write(f"wander: invoking {cli}...\n")
    raw = _invoke_claude(cli, WANDER_PROMPT)
    if not raw:
        sys.stderr.write(
            "wander: no reflection returned. The wandering is unfinished; try "
            "another sense organ.\n"
        )
        return 2

    summary, content = _split_reflection(raw)
    payload = {
        "kind": "wandering",
        "summary": summary,
        "content": content,
        "source": f"claude-cli:{os.path.basename(cli)}",
        "related_to": args.related_to,
    }
    result = _post_sensing(args.api, payload)
    if result:
        sys.stdout.write(
            f"wander: stored as sensing {result['id']}\n"
            f"        summary: {result['summary'][:120]}\n"
            f"        kind: wandering  source: {result['source']}\n"
        )
        return 0
    return 3


if __name__ == "__main__":
    sys.exit(main())

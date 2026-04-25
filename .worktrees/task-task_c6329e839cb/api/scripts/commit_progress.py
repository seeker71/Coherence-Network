#!/usr/bin/env python3
"""Commit pipeline progress to git. No-op when no changes or not a git repo.

Usage: Called by agent_runner after completed tasks when PIPELINE_AUTO_COMMIT=1.

  python scripts/commit_progress.py --task-id task_xxx --task-type impl --message "Add endpoint"

Exits 0 on success or no-op; 1 on git error (does not fail pipeline).
"""

import argparse
import logging
import os
import subprocess
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(_api_dir)
LOG_DIR = os.path.join(_api_dir, "logs")
LOG_FILE = os.path.join(LOG_DIR, "commit_progress.log")


def _setup_logging() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    log = logging.getLogger("commit_progress")
    log.setLevel(logging.INFO)
    if not log.handlers:
        h = logging.FileHandler(LOG_FILE, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
    return log


def run(cmd: list[str], cwd: str, log: logging.Logger) -> tuple[bool, str]:
    """Run command, return (success, output)."""
    try:
        r = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = (r.stdout or "").strip() + (f"\n{r.stderr}".strip() if r.stderr else "")
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        log.warning("Git command timed out")
        return False, "timeout"
    except Exception as e:
        log.warning("Git command failed: %s", e)
        return False, str(e)


def commit_progress(task_id: str, task_type: str, message: str, push: bool = False) -> bool:
    """Commit uncommitted changes. Returns True if committed (or no changes), False on error."""
    log = _setup_logging()
    if not os.path.isdir(os.path.join(PROJECT_ROOT, ".git")):
        log.debug("Not a git repo, skipping commit")
        return True

    ok, out = run(["git", "status", "--porcelain"], PROJECT_ROOT, log)
    if not ok:
        log.warning("git status failed: %s", out)
        return False
    if not out.strip():
        log.debug("No changes to commit")
        return True

    # Sanitize message for commit (single line, no newlines)
    safe_msg = (message or "pipeline progress")[:200].replace("\n", " ").strip()
    commit_msg = f"[pipeline] {task_type} {task_id}: {safe_msg}"

    ok, out = run(["git", "add", "-A"], PROJECT_ROOT, log)
    if not ok:
        log.warning("git add failed: %s", out)
        return False

    ok, out = run(["git", "commit", "-m", commit_msg], PROJECT_ROOT, log)
    if not ok:
        # May fail if nothing to commit (e.g. add didn't change index)
        if "nothing to commit" in out.lower():
            return True
        log.warning("git commit failed: %s", out)
        return False

    log.info("Committed: %s", commit_msg[:80])

    if push:
        ok, out = run(["git", "push"], PROJECT_ROOT, log)
        if not ok:
            log.warning("git push failed: %s", out)
            return False
        log.info("Pushed to remote")

    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Commit pipeline progress")
    ap.add_argument("--task-id", required=True, help="Task ID for commit message")
    ap.add_argument("--task-type", default="impl", help="Task type (spec/impl/test/review)")
    ap.add_argument("--message", default="", help="Short description")
    ap.add_argument("--push", action="store_true", help="Run git push after commit")
    args = ap.parse_args()

    ok = commit_progress(
        task_id=args.task_id,
        task_type=args.task_type,
        message=args.message or f"{args.task_type} completed",
        push=args.push,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

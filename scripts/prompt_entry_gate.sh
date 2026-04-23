#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/.."

usage() {
  cat <<'USAGE'
Usage: prompt_entry_gate.sh [--force-full]

Safe prompt-entry guard for Codex follow-up turns.

Behavior:
  - clean worktree: runs full preflight via auto_heal_start_gate.sh --with-pr-gate --with-rebase
  - dirty worktree: continuation mode (skip start-gate/rebase) and print required pre-commit gates
  - sibling dirty worktrees: print guidance by default; block only detached or unpushed-ahead siblings

Options:
  --force-full   run full preflight even when worktree is dirty (stashes/restores changes).
  -h, --help     show this help text.
USAGE
}

force_full=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-full)
      force_full=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "prompt-entry-gate: unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

cd "$REPO_ROOT"

print_claude_orientation() {
  if [[ ! -f "CLAUDE.md" ]]; then
    return
  fi
  echo "prompt-entry-gate: CLAUDE.md orientation:"
  echo "  - every file is memory in tissue; sense supple/tight before edits."
  echo "  - update the living form where it already exists before adding siblings."
  echo "  - compost superseded forms; keep counts where they are naturally tended."
  echo "  - ship reversible own-branch work through proof; pause for irreversible effects."
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "prompt-entry-gate: not inside a git worktree."
  exit 1
fi

if ! ./scripts/check_ghx_auth.sh; then
  echo "prompt-entry-gate: ghx auth smoke check failed."
  echo "Temporary override (not recommended): GHX_SKIP_AUTH_CHECK=1 make prompt-gate"
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
if [[ -z "$branch" ]]; then
  echo "prompt-entry-gate: failed to detect current branch name."
  exit 1
fi
if [[ "$branch" == "HEAD" ]]; then
  echo "prompt-entry-gate: detached HEAD detected."
  echo "Attach this worktree first:"
  echo "  git switch -c codex/<thread-name>"
  echo "  # or"
  echo "  git switch codex/<thread-name>"
  exit 1
fi

print_claude_orientation

if [[ "${PROMPT_GATE_SKIP_CONTINUITY:-0}" != "1" ]]; then
  continuity_args=(--fail-on-blocking-risk)
  if [[ "${PROMPT_GATE_CONTINUITY_STRICT:-0}" == "1" ]]; then
    continuity_args=(--fail-on-risk)
  fi
  if ! python3 scripts/worktree_continuity_guard.py "${continuity_args[@]}"; then
    echo "prompt-entry-gate: blocking sibling worktree continuity risk detected."
    echo "Dirty siblings are guidance, but detached or unpushed-ahead siblings can strand history."
    echo "Continue from that worktree, attach/push it, or merge/cherry-pick its branch before starting new work."
    echo "Temporary override (not recommended): PROMPT_GATE_SKIP_CONTINUITY=1 make prompt-gate"
    exit 1
  fi
else
  echo "prompt-entry-gate: continuity guard skipped via PROMPT_GATE_SKIP_CONTINUITY=1."
fi

if [[ "$force_full" == "1" ]]; then
  echo "prompt-entry-gate: force-full enabled; running full preflight."
  exec ./scripts/auto_heal_start_gate.sh --with-pr-gate --with-rebase
fi

if [[ -z "$(git status --short --untracked-files=all)" ]]; then
  echo "prompt-entry-gate: clean worktree; running full preflight."
  exec ./scripts/auto_heal_start_gate.sh --with-pr-gate --with-rebase
fi

echo "prompt-entry-gate: dirty worktree detected; continuation mode (skip start-gate/rebase)."
echo "prompt-entry-gate: continue implementation in this thread and run required gates before commit:"
echo "  git fetch origin main && git rebase origin/main"
echo "  python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main"
echo "  python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict"

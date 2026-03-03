#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: auto_heal_start_gate.sh [--with-pr-gate] [--with-rebase]

Run start-gate in a clean state by stashing local changes first, then restore
them (or keep the stash) after completion.

Options:
  --with-pr-gate     also run `worktree_pr_guard` in local mode.
  --with-rebase      also run `git fetch origin main` and `git rebase origin/main`
                     (typically for pre-push readiness checks).
  --skip-restore     skip automatic stash restoration at the end.
  --start-command CMD run this command instead of `make start-gate`.
                     May be passed multiple times for spaces, e.g.
                     --start-command make start-gate.
  -h, --help         show this help text.
EOF
}

run_pr_gate=0
run_rebase=0
run_restore=1
start_cmd=("make" "start-gate")
start_cmd_label="make start-gate"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-pr-gate)
      run_pr_gate=1
      shift
      ;;
    --with-rebase)
      run_rebase=1
      shift
      ;;
    --skip-restore)
      run_restore=0
      shift
      ;;
    --start-command)
      shift
      if [[ $# -eq 0 ]]; then
        echo "auto-heal-start-gate: --start-command requires a command token."
        exit 1
      fi
      start_cmd=("$1")
      start_cmd_label="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "auto-heal-start-gate: unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "auto-heal-start-gate: not inside a git worktree."
  exit 1
fi

restore_stash_if_needed() {
  local stash_ref="$1"
  local run_restore="$2"

  if [[ "$run_restore" != "1" ]]; then
    echo "auto-heal-start-gate: restore disabled; latest stash entry kept as ${stash_ref}."
    return
  fi

  if [[ -z "$stash_ref" ]]; then
    return
  fi

  echo "auto-heal-start-gate: restoring changes from ${stash_ref}."
  if ! git stash pop --index "$stash_ref"; then
    echo "auto-heal-start-gate: WARN: failed to restore ${stash_ref}; trying direct stash apply."
    git stash apply --index "$stash_ref" && git stash drop "$stash_ref"
  fi
}

cd "$SCRIPT_DIR/.."

status_output="$(git status --short --untracked-files=all)"
initial_clean="1"
if [[ -n "$status_output" ]]; then
  initial_clean="0"
fi

if [[ "$initial_clean" == "1" ]]; then
  echo "auto-heal-start-gate: worktree already clean. running start-gate directly."
  stash_ref=""
else
  stash_name="auto_heal_start_gate_$(date +%Y%m%dT%H%M%S)"
  echo "auto-heal-start-gate: stashing local changes: ${stash_name}"
  git stash push --include-untracked --message "$stash_name" >/dev/null
  stash_ref="$(git stash list -n 1 --format='stash@{%g}' 2>/dev/null | awk '{print $1}')"
  if [[ -z "$stash_ref" || "$stash_ref" == "stash@{}" ]]; then
    # Fallback for git versions without --format support.
    stash_ref="stash@{0}"
  fi
  echo "auto-heal-start-gate: changes stashed in ${stash_ref}."
fi

set +e
"${start_cmd[@]}"
start_rc=$?
set -e

if [[ "$start_rc" -ne 0 ]]; then
  restore_stash_if_needed "${stash_ref:-}" "$run_restore"
  exit "$start_rc"
fi

if [[ "$run_rebase" == "1" ]]; then
  echo "auto-heal-start-gate: running required rebase refresh."
  set +e
  git fetch origin main
  git rebase origin/main
  rebase_rc=$?
  set -e
  if [[ "$rebase_rc" -ne 0 ]]; then
    restore_stash_if_needed "${stash_ref:-}" "$run_restore"
    exit "$rebase_rc"
  fi
fi

if [[ "$run_pr_gate" == "1" ]]; then
  echo "auto-heal-start-gate: running local pr guard."
  set +e
  python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
  pr_rc=$?
  set -e
  if [[ "$pr_rc" -ne 0 ]]; then
    restore_stash_if_needed "${stash_ref:-}" "$run_restore"
    exit "$pr_rc"
  fi
fi

restore_stash_if_needed "${stash_ref:-}" "$run_restore"

if [[ "$initial_clean" == "1" ]]; then
  echo "auto-heal-start-gate: completed in clean state; no restore required."
fi
echo "auto-heal-start-gate: completed."
echo "auto-heal-start-gate: command used -> ${start_cmd_label}"
if [[ "$run_rebase" == "1" ]]; then
  echo "auto-heal-start-gate: rebase refresh executed."
fi
if [[ "$run_pr_gate" == "1" ]]; then
  echo "auto-heal-start-gate: local worktree guard executed."
fi

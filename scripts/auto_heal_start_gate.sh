#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'USAGE'
Usage: auto_heal_start_gate.sh [--with-pr-gate] [--with-rebase] [--skip-restore] [--start-command CMD]

Run start-gate in a clean worktree, stashing local changes first and restoring them
afterward.

Options:
  --with-pr-gate     also run `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main`.
  --with-rebase      also run `git fetch origin main` and `git rebase origin/main`.
  --skip-restore     do not restore stashed worktree changes after completion.
  --start-command CMD command string to run instead of start-gate (default: make start-gate)
  -h, --help         show this help text.
USAGE
}

run_pr_gate=0
run_rebase=0
run_restore=1
start_cmd="make start-gate"
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
        echo "auto-heal-start-gate: --start-command requires a command string"
        exit 1
      fi
      start_cmd="$1"
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
  local restore_flag="$2"

  if [[ "$restore_flag" != "1" ]]; then
    echo "auto-heal-start-gate: restore disabled; latest stash entry kept as ${stash_ref}."
    return
  fi

  if [[ -z "$stash_ref" ]]; then
    return
  fi

  echo "auto-heal-start-gate: restoring changes from ${stash_ref}."
  if ! git stash pop --index "$stash_ref"; then
    echo "auto-heal-start-gate: WARN: pop failed, trying apply+drop for ${stash_ref}."
    git stash apply --index "$stash_ref" && git stash drop "$stash_ref"
  fi
}

cd "$SCRIPT_DIR/.."

initial_clean=0
if [[ -z "$(git status --short --untracked-files=all)" ]]; then
  initial_clean=1
fi

stash_ref=""
if [[ "$initial_clean" == "1" ]]; then
  echo "auto-heal-start-gate: worktree already clean."
else
  stash_name="auto_heal_start_gate_$(date +%Y%m%dT%H%M%S)"
  echo "auto-heal-start-gate: stashing local changes as ${stash_name}."
  git stash push --include-untracked --message "$stash_name" >/dev/null
  stash_ref="stash@{0}"
  echo "auto-heal-start-gate: changes stashed in ${stash_ref}."
fi

set +e
bash -lc "$start_cmd"
start_rc=$?
set -e
if [[ "$start_rc" -ne 0 ]]; then
  restore_stash_if_needed "$stash_ref" "$run_restore"
  exit "$start_rc"
fi

if [[ "$run_rebase" == "1" ]]; then
  echo "auto-heal-start-gate: running git fetch/rebase refresh."
  set +e
  git fetch origin main
  git rebase origin/main
  rebase_rc=$?
  set -e
  if [[ "$rebase_rc" -ne 0 ]]; then
    restore_stash_if_needed "$stash_ref" "$run_restore"
    exit "$rebase_rc"
  fi
fi

if [[ "$run_pr_gate" == "1" ]]; then
  echo "auto-heal-start-gate: running worktree-pr-guard (local)."
  set +e
  python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
  pr_gate_rc=$?
  set -e
  if [[ "$pr_gate_rc" -ne 0 ]]; then
    restore_stash_if_needed "$stash_ref" "$run_restore"
    exit "$pr_gate_rc"
  fi
fi

restore_stash_if_needed "$stash_ref" "$run_restore"

echo "auto-heal-start-gate: completed."
echo "auto-heal-start-gate: command used -> ${start_cmd_label}"
if [[ "$run_rebase" == "1" ]]; then
  echo "auto-heal-start-gate: git fetch/rebase executed."
fi
if [[ "$run_pr_gate" == "1" ]]; then
  echo "auto-heal-start-gate: local worktree gate executed."
fi
if [[ "$initial_clean" == "1" ]]; then
  echo "auto-heal-start-gate: no changes to restore."
fi

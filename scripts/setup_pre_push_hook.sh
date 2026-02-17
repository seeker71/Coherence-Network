#!/usr/bin/env bash
set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git worktree." >&2
  exit 1
fi

git config core.hooksPath .githooks
chmod +x .githooks/pre-push
echo "Configured core.hooksPath to .githooks and enabled pre-push guard."
echo "Disable with: git config --unset core.hooksPath or SKIP_PR_GUARD=1 for emergency bypass."

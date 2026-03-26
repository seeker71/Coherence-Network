#!/usr/bin/env bash
# Publish skills/coherence-network to ClawHub when token is set. Skips if CLAWHUB_TOKEN empty.
# Uses npx when clawhub is not on PATH (package name may evolve — see specs/157).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKILL_DIR="${ROOT}/skills/coherence-network"

if [[ ! -d "$SKILL_DIR" ]]; then
  echo "No skill directory at $SKILL_DIR"
  exit 1
fi

if [[ -z "${CLAWHUB_TOKEN:-}" ]]; then
  echo "::error::CLAWHUB_TOKEN is required when this job runs (skill paths changed on main)."
  exit 1
fi

export CLAWHUB_TOKEN
cd "$SKILL_DIR"

if command -v clawhub >/dev/null 2>&1; then
  exec clawhub publish .
fi

# Fallback: npx (adjust package if upstream renames the CLI)
exec npx --yes clawhub@latest publish .

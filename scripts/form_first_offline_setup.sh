#!/usr/bin/env bash
# form_first_offline_setup.sh — bring the body home so Form-first answers OFFLINE.
#
# Point a cloud environment's SETUP SCRIPT at this (Claude Code: Environment → setup
# script; Codex: the setup phase, which has network while the agent phase does not).
# It populates the per-clone local lattice from the repo's OWN content, so the
# Form-first router (`form-cli ask`) and the substrate doors ground in the body
# WITHOUT crossing the sandbox egress boundary — no allowlist, no reach to
# api.coherencycoin.com. A body that travels whole needs no trust list.
#
# Idempotent: a populated lattice is an instant no-op. Carrier only — the routing is
# Form (form-cli-router / form-cli-sufficiency, four-way proven); this brings the
# content home so that routing has a body to read.
#
# Scope (env FORM_FIRST_INGEST):
#   concepts  (default) — the vision-kb body; covers most "what is X / shape of X" asks, fast
#   all                 — the whole body (concepts, specs, ideas, presences, lineages); thorough, slower
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 0

# already home? (cells_total > 0) → instant no-op
if python3 scripts/coh_substrate.py stats 2>/dev/null | grep -qE "cells_total: [1-9]"; then
  echo "⟐ local body already home (lattice populated) — offline Form-first ready, no allowlist needed."
  exit 0
fi

# the substrate CLI needs the api package importable; ensure it best-effort, stay quiet on success
if ! python3 -c "import app.services.substrate" >/dev/null 2>&1; then
  python3 -m pip install -e api -q >/dev/null 2>&1 || true
fi

SCOPE="${FORM_FIRST_INGEST:-concepts}"
case "$SCOPE" in
  all) FLAG="--all" ;;
  *)   FLAG="--concepts" ;;
esac

echo "⟐ bringing the body home: ingesting the repo's own content (${SCOPE}) into the local lattice — offline, one-time…"
if python3 scripts/coh_substrate.py ingest "$FLAG" >/dev/null 2>&1; then
  N="$(python3 scripts/coh_substrate.py stats 2>/dev/null | grep -oE 'cells_total: [0-9]+' | grep -oE '[0-9]+')"
  echo "⟐ done — ${N:-some} cells home. Form-first now answers from the local body; no egress allowlist required."
else
  echo "⟐ ingest unavailable here (missing python deps or toolchain) — Form-first will fall back to the public read door if egress is allowed, else to remote reasoning."
fi
exit 0

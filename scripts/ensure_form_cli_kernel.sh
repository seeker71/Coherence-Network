#!/usr/bin/env bash
# ensure_form_cli_kernel.sh — warm the c-bootstrap fkwu form-cli (agent runtime).
# bin-go is maintainer/bootstrap compost only — not warmed on this surface.
# Kernel-owned maintainer carriers live under form/scripts/regen_*.sh.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/ensure_form_cli_native.sh"

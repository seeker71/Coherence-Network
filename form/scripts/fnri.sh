#!/bin/sh
# Composted carrier: pipe fnri subcommand to form-cli (logic in fnri-shell.fk).
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec "$ROOT/scripts/form-cli-run.sh" fnri "$@"

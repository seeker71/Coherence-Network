#!/usr/bin/env bash
# grow_nl_lexicon.sh — LAUNCHER ONLY. All projection LOGIC is Form:
#   form-stdlib/nl-lexicon-grow.fk (the recipe, four-way proven by nl-lexicon-grow-band.fk)
#   scripts/grow_nl_lexicon.fk      (the runner: read_file -> grow -> write_file_text)
# This script does no logic — it builds the kernel if needed and runs the Form program.
# Running the kernel binary IS the host exec, a carrier-not-debt (host-kernel.form).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"
[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && GOPROXY=off go build -o bin-go . )
cd "$ROOT" && "$GO" form/form-stdlib/json.fk form/form-stdlib/string-case.fk \
    form/form-stdlib/nl-lexicon-grow.fk scripts/grow_nl_lexicon.fk

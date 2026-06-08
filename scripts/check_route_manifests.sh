#!/usr/bin/env bash
# check_route_manifests.sh — gate the kernel-router manifests against unbound symbols.
#
# Runs the kernel's compile-time name-resolution gate (`form-kernel-rust check`, the
# #2581 pass that runs name-check.fk over a lowered manifest) on every route manifest.
# The lazy evaluator only raises `unbound: <name>` when the walk reaches that node at
# serve time, so without this a manifest with a dangling reference compiles and only
# fails in production — the silent-rot class that left production-routes.fk non-loading
# for days. This is the ratchet: it blocks NEW broken manifests at the build gate.
#
# A manifest PASSES iff `check` exits 0 (every name resolves). Keying on the exit code
# (not on parsing "unbound:" lines) is deliberate: a manifest can fail the gate two
# ways — a clean "unbound: <name>" report, OR a hard compile panic (e.g. the form.route
# section-compile's g-parse gap) — and both must be caught.
#
# The baseline (deploy/kernel-router/.namecheck-baseline) lists manifests with a KNOWN,
# tracked failure — currently production-routes.fk, whose form.route class->route
# lowering is broken (codex's source-compiler core; see the file's note). A baselined
# manifest is reported but does not fail the build; a NON-baselined failure does. When
# the known gap is fixed, remove its line: the manifest must then stay clean. The
# ratchet only ever tightens.
#
# Run standalone:  scripts/check_route_manifests.sh   (builds the kernel if stale)
# Designed to also be called from form/validate.sh (the proof harness, which already
# builds the kernel), so the gate runs as part of the three-way proof.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
RS_BIN="$FORMDIR/form-kernel-rust/target/release/form-kernel-rust"
MANIFEST_DIR="$ROOT/deploy/kernel-router"
BASELINE="$MANIFEST_DIR/.namecheck-baseline"
STDLIB="form-stdlib"

if [[ ! -x "$RS_BIN" || "$FORMDIR/form-kernel-rust/src/main.rs" -nt "$RS_BIN" ]]; then
    echo "  building rust kernel for manifest check..." >&2
    (cd "$FORMDIR/form-kernel-rust" && cargo build --release --quiet)
fi

# baselined? (manifest basenames, '#' comments and blank lines ignored)
is_baselined() { grep -v '^[[:space:]]*#' "$BASELINE" 2>/dev/null | grep -qxF "$1"; }

cd "$FORMDIR"
fail=0
shopt -s nullglob
for manifest in "$MANIFEST_DIR"/*.fk; do
    base="$(basename "$manifest")"
    out="$("$RS_BIN" check --routes "$manifest" --stdlib "$STDLIB" 2>&1)"
    rc=$?
    if [[ $rc -eq 0 ]]; then
        echo "  ✓ $base — every name resolves" >&2
    elif is_baselined "$base"; then
        echo "  • $base — KNOWN failure (baselined, tracked; awaiting fix):" >&2
        printf '%s\n' "$out" | sed 's/^/      /' | head -3 >&2
    else
        echo "  ✗ $base — FAILS the name-check gate (would not load / would panic at serve):" >&2
        printf '%s\n' "$out" | sed 's/^/      /' | head -5 >&2
        fail=1
    fi
done

if [[ "$fail" -ne 0 ]]; then
    echo "  manifest name-check: a manifest fails the gate — fix the dangling reference," >&2
    echo "  or (if a known, tracked gap) add its basename to $BASELINE" >&2
fi
exit $fail

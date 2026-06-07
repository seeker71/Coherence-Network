#!/usr/bin/env bash
# orchestrate.sh — run cells A and B as SEPARATE kernel processes,
# chained via file-backed channels. The kernel command is passed as
# arguments to this script so the same orchestration runs through
# Go, Rust, or TS kernels.
#
# Usage:
#   ./orchestrate.sh <kernel-cmd...>
#
# Examples:
#   ./orchestrate.sh ../../../form-kernel-go/bin-go
#   ./orchestrate.sh ../../../form-kernel-rust/target/release/form-kernel-rust
#   ./orchestrate.sh node --stack_size=262144 \
#       --import ../../../form-kernel-ts/node_modules/tsx/dist/loader.mjs \
#       ../../../form-kernel-ts/src/main.ts
#
# The script:
#   1. Cleans /tmp/ topology files (idempotent restart).
#   2. Runs setup.fk        → registers B in the registry.
#   3. Runs cell-a-send.fk  → A queries the registry, sends a QUERY.
#   4. Runs cell-b-handle.fk → B reads its channel, writes a RESPONSE.
#   5. Runs cell-a-receive.fk → A reads the reply, looks up symbols.
#
# Each step is its own kernel invocation. The substrate state is fresh
# at the start of each step; the only durable knowledge is the .fkb
# files on disk. Content-addressing makes the NodeIDs converge across
# processes — this is what "distributed" means in the cell sense.
#
# Exits 0 on success, 1 if any step fails or the final verdict ≠ 8.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <kernel-cmd...>" >&2
    exit 2
fi

# Resolve script dir so the .fk paths work regardless of cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORM_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Kernel command — everything we receive, treated as an argv prefix.
KERNEL_CMD=("$@")

# Preludes for each step. Each step is invoked with the kernel command,
# then the prelude list, then the step's .fk file. core.fk uses a
# `section [...]` block that needs source-compilation into a
# kernel-walkable form first; the other stdlib files are already in
# the BML S-expr dialect the kernels walk directly.
CORE_SRC="$FORM_DIR/form-stdlib/core.fk"
CHANNEL="$FORM_DIR/form-stdlib/channel.fk"
REGISTRY="$FORM_DIR/form-stdlib/cell-registry.fk"
SHA="$FORM_DIR/form-stdlib/sha256.fk"
QUERY="$FORM_DIR/form-stdlib/channel-query.fk"
SYMBOLS="$FORM_DIR/form-stdlib/symbols.fk"

# Compile core.fk once — every step needs it (append, nil?, etc.).
# We always use the Go kernel for the source-compile pre-step because
# it's the canonical source-compiler driver. The compiled artifact is
# kernel-agnostic; all three siblings walk it identically. The compile
# step must run with cwd=FORM_DIR so the source-compiler resolves
# form-ontology.json and other relative resources correctly.
GO_BIN_FOR_COMPILE="$FORM_DIR/form-kernel-go/bin-go"
COMPILE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/form-28-compile.XXXXXX")"
trap 'rm -rf "$COMPILE_DIR"' EXIT

CORE="$COMPILE_DIR/core.compiled.fk"
COMPILE_DRIVER="$COMPILE_DIR/compile-core.fk"
printf '(do (form-source-compile-file "%s" "%s"))\n' "$CORE_SRC" "$CORE" > "$COMPILE_DRIVER"
(
    cd "$FORM_DIR"
    "$GO_BIN_FOR_COMPILE" \
        "form-stdlib/json.fk" \
        "form-stdlib/cache.fk" \
        "form-stdlib/form-ontology-loader.fk" \
        "form-stdlib/line-grammar.fk" \
        "form-stdlib/bmf-core.fk" \
        "form-stdlib/bmf-grammar.fk" \
        "form-stdlib/bml.fk" \
        "form-stdlib/source-compiler.fk" \
        "$COMPILE_DRIVER" >/dev/null
)

# Clean the topology files so re-runs are reproducible.
rm -f /tmp/28-dist-registry.fkb \
      /tmp/28-dist-cell-b.fkb \
      /tmp/28-dist-cell-a-reply.fkb

run_step() {
    local label="$1"; shift
    echo "--- $label ---"
    "${KERNEL_CMD[@]}" "$@"
}

# Step 1: setup — register B in the registry.
run_step "setup" "$CORE" "$CHANNEL" "$REGISTRY" \
    "$SCRIPT_DIR/setup.fk"

# Step 2: cell-a-send — A queries the registry, sends a QUERY to B.
run_step "cell-a-send" "$CORE" "$CHANNEL" "$REGISTRY" "$SHA" "$QUERY" \
    "$SCRIPT_DIR/cell-a-send.fk"

# Step 3: cell-b-handle — B reads its channel, writes a RESPONSE.
run_step "cell-b-handle" "$CORE" "$CHANNEL" "$REGISTRY" "$SHA" "$QUERY" "$SYMBOLS" \
    "$SCRIPT_DIR/cell-b-handle.fk"

# Step 4: cell-a-receive — A reads the reply, looks up symbols.
run_step "cell-a-receive" "$CORE" "$CHANNEL" "$REGISTRY" "$SHA" "$QUERY" "$SYMBOLS" \
    "$SCRIPT_DIR/cell-a-receive.fk"

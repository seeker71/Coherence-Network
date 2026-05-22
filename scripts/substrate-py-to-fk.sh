#!/usr/bin/env bash
# substrate-py-to-fk.sh — convert a substrate Python file to .fk via the
# universal codec lattice.
#
# Usage:
#   scripts/substrate-py-to-fk.sh <path-to.py>
#
# Pipeline:
#   convert.fk reads <path>, dispatches to grammars/python.fk parser,
#   produces a universal-shapes Recipe tree. emits/form.fk's
#   form-templates render the tree back as Form (.fk) source via
#   emit-engine.fk's recursive walker. Output to stdout; redirect to
#   capture as a .fk file.
#
# Coverage today (2026-05-22): grammars/python.fk handles the file-
# header subset (module docstring, imports, def-headers, class
# headers, simple assignments, comments). Full function bodies and
# class bodies will compose as grammars/python.fk grows. The pipeline
# itself is data-driven — each grammar enhancement increases coverage
# without changing this script.

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "usage: $0 <path-to.py>" >&2
    exit 1
fi

TARGET="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KERNEL="$ROOT/experiments/form-kernel-go/bin-go"
STDLIB="$ROOT/experiments/form-stdlib"

if [ ! -x "$KERNEL" ]; then
    echo "building form-kernel-go..." >&2
    (cd "$ROOT/experiments/form-kernel-go" && go build -o bin-go .)
fi

# Generate a per-invocation converter script with the target path baked in.
SCRIPT="$(mktemp -t substrate-py-to-fk.XXXXXX.fk)"
trap 'rm -f "$SCRIPT"' EXIT

cat > "$SCRIPT" <<EOF
(do
    (let target-path "$TARGET")
    (let registry (list (list "form" form-templates)))
    (let cell (convert target-path))
    (let fk-text (emit-to "form" cell registry))
    (print fk-text)
    (str_len fk-text))
EOF

# Single bin-go invocation loads the universal codec lattice and the
# converter script. The kernel prints fk-text via the (print) native;
# the final str_len lands on stdout as the trailing line.
exec "$KERNEL" \
    "$STDLIB/core.fk" \
    "$STDLIB/emit-engine.fk" \
    "$STDLIB/codec.fk" \
    "$STDLIB/grammars/json.fk" \
    "$STDLIB/grammars/python.fk" \
    "$STDLIB/emit.fk" \
    "$STDLIB/emits/form.fk" \
    "$STDLIB/convert.fk" \
    "$SCRIPT"

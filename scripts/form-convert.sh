#!/usr/bin/env bash
# form-convert — the machine-native kernel-cli for the goal Urs named:
# convert any repo file to native Form cells via one invocation, with
# full source-coordinate traceability.
#
# Usage:
#   scripts/form-convert.sh <file>
#   scripts/form-convert.sh --kernel rust|go|ts <file>
#
# Dispatches on file extension to load only the grammar needed for
# this file, then runs convert.fk's (convert path). Per-invocation
# grammar loading sidesteps cross-grammar name collisions.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPERIMENTS="$REPO_ROOT/experiments"

KERNEL="rust"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --kernel) KERNEL="$2"; shift 2 ;;
        --help|-h)
            cat <<EOF
form-convert — convert any repo file to native Form cells
Usage: $0 [--kernel rust|go|ts] <file>
Extensions: .md .json .yml .yaml .fk .py .ts .tsx .rs .go .png
EOF
            exit 0
            ;;
        *) FILE="$1"; shift ;;
    esac
done

[[ -z "${FILE:-}" ]] && { echo "usage: form-convert [--kernel rust|go|ts] <file>" >&2; exit 1; }
[[ ! -f "$FILE" ]] && { echo "form-convert: file not found: $FILE" >&2; exit 2; }

ABS_FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"
REL_FILE="${ABS_FILE#$EXPERIMENTS/}"

ext="${FILE##*.}"
case "$ext" in
    md)        GRAMMARS=(grammars/markdown.fk) ;;
    json)      GRAMMARS=(grammars/json.fk) ;;
    yml|yaml)  GRAMMARS=(grammars/yaml.fk) ;;
    fk)        GRAMMARS=(grammars/form.fk) ;;
    py)        GRAMMARS=(grammars/python.fk) ;;
    ts|tsx)    GRAMMARS=(grammars/typescript.fk) ;;
    rs)        GRAMMARS=(grammars/rust.fk) ;;
    go)        GRAMMARS=(grammars/go.fk) ;;
    png)       GRAMMARS=(grammars/png.fk) ;;
    *)         echo "form-convert: unknown extension '$ext'" >&2; exit 3 ;;
esac

LOAD_ARGS=(form-stdlib/core.fk form-stdlib/cell-trace.fk)
for g in "${GRAMMARS[@]}"; do LOAD_ARGS+=("form-stdlib/$g"); done
LOAD_ARGS+=(form-stdlib/convert.fk)

RUNNER=$(mktemp /tmp/form-convert-runner.XXXXXX.fk)
trap "rm -f $RUNNER" EXIT
cat > "$RUNNER" <<EOF
(do
    (let root (convert "$REL_FILE"))
    (let kids (node_children root))
    (let count (len kids))
    (let first-src (if (eq count 0) "" (cell-source (head kids))))
    (print "form-convert summary:")
    (print "  file:")
    (print "$REL_FILE")
    (print "  child count:")
    (print count)
    (print "  first child source:")
    (print first-src)
    count)
EOF

case "$KERNEL" in
    rust) BIN="$EXPERIMENTS/form-kernel-rust/target/release/form-kernel-rust" ;;
    go)   BIN="$EXPERIMENTS/form-kernel-go/bin-go" ;;
    ts)   echo "form-convert: ts kernel not yet wired" >&2; exit 4 ;;
    *)    echo "form-convert: unknown kernel '$KERNEL'" >&2; exit 4 ;;
esac

cd "$EXPERIMENTS"
"$BIN" "${LOAD_ARGS[@]}" "$RUNNER"

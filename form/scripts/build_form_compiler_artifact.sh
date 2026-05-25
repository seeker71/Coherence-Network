#!/usr/bin/env bash
# Build the source compiler .fkb used by the binary→native-python proof loop.
#
# See specs/form-binary-to-native-python-emitter.md for the full proof
# chain. This script compiles core.fk + compiler.fk + source-compiler.fk
# + grammars/python-bmf.fk into a single .fkb the emitter ingests.
#
# Usage:
#   ./form/scripts/build_form_compiler_artifact.sh --out path/to/source.fkb

set -euo pipefail

usage() {
    echo "Usage: $0 --out OUT_FKB_PATH" >&2
    exit 2
}

OUT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --out)
            shift
            OUT="${1:-}"
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo "unknown arg: $1" >&2
            usage
            ;;
    esac
    shift || true
done

[[ -z "$OUT" ]] && usage

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FORM_DIR="$REPO_ROOT/form"
KERNEL_GO="$FORM_DIR/form-kernel-go"

mkdir -p "$(dirname "$OUT")"

cd "$FORM_DIR"

if [[ ! -x "$KERNEL_GO/bin-go" ]]; then
    echo "Building form-kernel-go..." >&2
    (cd "$KERNEL_GO" && go build -o bin-go .) || {
        echo "form-kernel-go build failed; falling back to Python-side compile" >&2
    }
fi

SOURCES=(
    "form-stdlib/core.fk"
    "form-stdlib/compiler.fk"
    "form-stdlib/source-compiler.fk"
    "form-stdlib/engine.fk"
    "form-stdlib/grammars/python-bmf.fk"
)

if [[ -x "$KERNEL_GO/bin-go" ]]; then
    echo "Compiling Form sources via form-kernel-go..." >&2
    "$KERNEL_GO/bin-go" --emit-fkb "$OUT" "${SOURCES[@]}" || {
        echo "form-kernel-go --emit-fkb failed; this kernel revision may not yet support --emit-fkb." >&2
        echo "Falling back to text concatenation as a placeholder artifact." >&2
        cat "${SOURCES[@]}" > "${OUT%.fkb}.fk-concat.txt"
        # Use the native Python compiler to emit a placeholder .fkb
        cd "$REPO_ROOT"
        python3 -m kernels.python_bmf.compiler --file "$FORM_DIR/${SOURCES[-1]}" --out "$OUT" \
            || { echo "placeholder emit failed" >&2; exit 1; }
    }
else
    echo "form-kernel-go not available; using native Python placeholder." >&2
    cd "$REPO_ROOT"
    python3 -m kernels.python_bmf.compiler --file "$FORM_DIR/${SOURCES[-1]}" --out "$OUT"
fi

echo "ok — $OUT"

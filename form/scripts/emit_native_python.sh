#!/usr/bin/env bash
# Run the Form-native emitter to produce kernels/python_bmf/*.py.
#
# Reads form/form-stdlib/emits/python-native.fk (the emitter recipes)
# and writes Python source via the kernel's write_file_text host
# primitive. The kernel CWD is the repo root so target paths in
# emits/python-native.fk resolve correctly.
#
# Source-compiles core.fk first (same shape validate.sh uses) so the
# emitter has nil?/map/foldl/etc. available.
#
# Usage:
#   form/scripts/emit_native_python.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

GO_BIN="$REPO_ROOT/form/form-kernel-go/bin-go"
if [[ ! -x "$GO_BIN" ]]; then
    echo "Building form-kernel-go..." >&2
    (cd "$REPO_ROOT/form/form-kernel-go" && go build -o bin-go .)
fi

WORK_DIR="$REPO_ROOT/form/.cache/emit_native_python"
mkdir -p "$WORK_DIR" kernels/python_bmf

# Source-compile core.fk into a kernel-ready .fk (same path validate.sh uses).
CORE_COMPILED="$WORK_DIR/core.compiled.fk"
CORE_DRIVER="$WORK_DIR/core-driver.fk"
printf '(do (form-source-compile-file "%s" "%s"))\n' \
    "$REPO_ROOT/form/form-stdlib/core.fk" "$CORE_COMPILED" > "$CORE_DRIVER"

(cd "$REPO_ROOT/form" && "$GO_BIN" "form-stdlib/source-compiler.fk" "$CORE_DRIVER" >/dev/null)

EMITTER="$REPO_ROOT/form/form-stdlib/emits/python-native.fk"
DRIVER="$REPO_ROOT/form/form-stdlib/emits/python-native-driver.fk"

echo "Running Form-native emitter..." >&2
(cd "$REPO_ROOT" && "$GO_BIN" "$CORE_COMPILED" "$EMITTER" "$DRIVER")

echo "Emitted:" >&2
ls -la kernels/python_bmf/objects.py 2>&1 | tail -1
echo ""
echo "Verifying emitted Python compiles..." >&2
python3 -m py_compile kernels/python_bmf/objects.py
echo "  ok"

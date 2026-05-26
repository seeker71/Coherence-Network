#!/usr/bin/env bash
# Run the Form-native emitter to produce kernels/python_bmf/objects.py.
#
# Phase 1 pipeline (specs/form-binary-to-native-python-emitter.md):
#
#   form-ontology.json
#     └─ build_form_compiler_artifact.sh --categories
#        └─ python-bmf-categories.fk  (generated)
#           └─ form-kernel-go --emit-binary
#              └─ python-bmf-categories.fkb  (the substrate ice)
#                 └─ read_form_binary inside python-native.fk
#                    └─ pn-cat-table-from-artifact (lens)
#                       └─ pn-emit-objects-module (emitter)
#                          └─ write_file_text → kernels/python_bmf/objects.py
#
# No Form literal of the category table lives in the emitter — the
# lattice IS the source of truth, the .fkb is its serialized projection.
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

# Step 0: source-compile core.fk (same shape validate.sh uses) so
# the emitter has nil?/map/foldl/etc. available at walk time.
CORE_COMPILED="$WORK_DIR/core.compiled.fk"
CORE_DRIVER="$WORK_DIR/core-driver.fk"
printf '(do (form-source-compile-file "%s" "%s"))\n' \
    "$REPO_ROOT/form/form-stdlib/core.fk" "$CORE_COMPILED" > "$CORE_DRIVER"
(cd "$REPO_ROOT/form" && "$GO_BIN" \
    "form-stdlib/json.fk" \
    "form-stdlib/cache.fk" \
    "form-stdlib/form-ontology-loader.fk" \
    "form-stdlib/source-compiler.fk" \
    "$CORE_DRIVER" >/dev/null)

# Step 1: build the .fkb that carries python.bmf categories.
CATS_FKB="$WORK_DIR/python-bmf-categories.fkb"
echo "Step 1: building $CATS_FKB from form-ontology.json..." >&2
"$REPO_ROOT/form/scripts/build_form_compiler_artifact.sh" --categories "$CATS_FKB" >&2

# Step 2: run the Form emitter against the .fkb.
EMITTER="$REPO_ROOT/form/form-stdlib/emits/python-native.fk"
DRIVER="$REPO_ROOT/form/form-stdlib/emits/python-native-driver.fk"

echo "Step 2: running Form-native emitter (kernel: form-kernel-go)..." >&2
(cd "$REPO_ROOT" && "$GO_BIN" "$CORE_COMPILED" "$EMITTER" "$DRIVER")

echo "" >&2
echo "Emitted:" >&2
ls -la kernels/python_bmf/objects.py 2>&1 | tail -1
echo "" >&2
echo "Step 3: py_compile sanity check..." >&2
python3 -m py_compile kernels/python_bmf/objects.py
echo "  ok — objects.py compiles" >&2

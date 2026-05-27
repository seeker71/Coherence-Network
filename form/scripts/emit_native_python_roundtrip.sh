#!/usr/bin/env bash
# Universal-translator proof-of-shape: drive a Form recipe through the
# python-native emitter, run the emitted Python under CPython, and confirm
# the values match what the Form kernel walks the same recipe to.
#
# Pipeline:
#
#   Form recipe (source text inside python-native-roundtrip-driver.fk)
#     └─ pn-emit-string (in python-native.fk)
#        └─ writes kernels/python_bmf/_emitted_roundtrip.py
#           └─ python3 imports it, calls add(2,3), factorial(5), factorial(10)
#              └─ values match form-kernel-go evaluating the same recipes
#
# See kernels/UNIVERSAL_TRANSLATOR_ROUNDTRIP.md for the wider gap-map from
# "one recipe" to "the BMF compiler-compiler itself".
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

GO_BIN="$REPO_ROOT/form/form-kernel-go/bin-go"
if [[ ! -x "$GO_BIN" ]]; then
    echo "Building form-kernel-go..." >&2
    (cd "$REPO_ROOT/form/form-kernel-go" && go build -o bin-go .)
fi

WORK_DIR="$REPO_ROOT/form/.cache/emit_native_python"
CORE_COMPILED="$WORK_DIR/core.compiled.fk"
CORE_DRIVER="$WORK_DIR/core-driver.fk"

# Step 0: ensure core is source-compiled (same shape emit_native_python.sh uses).
if [[ ! -f "$CORE_COMPILED" ]]; then
    mkdir -p "$WORK_DIR" kernels/python_bmf
    printf '(do (form-source-compile-file "%s" "%s"))\n' \
        "$REPO_ROOT/form/form-stdlib/core.fk" "$CORE_COMPILED" > "$CORE_DRIVER"
    (cd "$REPO_ROOT/form" && "$GO_BIN" \
        "form-stdlib/json.fk" \
        "form-stdlib/cache.fk" \
        "form-stdlib/form-ontology-loader.fk" \
        "form-stdlib/source-compiler.fk" \
        "$CORE_DRIVER" >/dev/null)
fi

EMITTER="$REPO_ROOT/form/form-stdlib/emits/python-native.fk"
DRIVER="$REPO_ROOT/form/form-stdlib/emits/python-native-roundtrip-driver.fk"

echo "Step 1: walk Form recipe → idiomatic Python via pn-emit-string..." >&2
(cd "$REPO_ROOT" && "$GO_BIN" "$CORE_COMPILED" "$EMITTER" "$DRIVER")

EMITTED="$REPO_ROOT/kernels/python_bmf/_emitted_roundtrip.py"
echo "" >&2
echo "Emitted:" >&2
cat "$EMITTED"
echo "" >&2

echo "Step 2: run the emitted Python under CPython..." >&2
PY_OUT=$(python3 -c "
import sys, types
sdk = types.ModuleType('kernels.python_bmf.sdk')
sys.modules['kernels'] = types.ModuleType('kernels')
sys.modules['kernels.python_bmf'] = types.ModuleType('kernels.python_bmf')
sys.modules['kernels.python_bmf'].sdk = sdk
sys.modules['kernels.python_bmf.sdk'] = sdk
import importlib.util
spec = importlib.util.spec_from_file_location('emitted', '$EMITTED')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.add(2, 3))
print(mod.factorial(5))
print(mod.factorial(10))
")
echo "$PY_OUT"

echo "" >&2
echo "Step 3: walk the same recipes through form-kernel-go..." >&2
FORM_DRIVER="$WORK_DIR/roundtrip-eval.fk"
cat > "$FORM_DRIVER" <<'FKEOF'
(do
    (defn add (a b) (add a b))
    (defn factorial (n) (if (le n 1) 1 (mul n (factorial (sub n 1)))))
    (print (add 2 3))
    (print (factorial 5))
    (print (factorial 10)))
FKEOF
FORM_RAW=$("$GO_BIN" "$FORM_DRIVER" 2>/dev/null)
FORM_OUT=$(echo "$FORM_RAW" | grep -E '^[0-9]+$' | head -n 3)
echo "$FORM_OUT"

echo "" >&2
echo "Step 4: compare." >&2
if [[ "$PY_OUT" == "$FORM_OUT" ]]; then
    echo "  ok — CPython and form-kernel-go produce identical values" >&2
    echo "  add(2,3)=5  factorial(5)=120  factorial(10)=3628800" >&2
else
    echo "  MISMATCH" >&2
    diff <(echo "$PY_OUT") <(echo "$FORM_OUT") >&2 || true
    exit 1
fi

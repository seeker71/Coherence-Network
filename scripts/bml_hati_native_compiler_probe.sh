#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
GO="$FORM/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"

if [[ ! -x "$GO" ]]; then
  (cd "$FORM/form-kernel-go" && go build -o bin-go .)
fi

if ! command -v "$CLANG" >/dev/null 2>&1; then
  echo "FAIL: clang is required for the native Hati binary probe" >&2
  exit 1
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/bml-hati-native.XXXXXX")"
trap 'rm -rf "$work"' EXIT

driver="$work/bml-hati-native-driver.fk"
out="$work/driver.out"
compiled_core="$work/core.lowered.fk"
compiled_compiler="$work/compiler.lowered.fk"
compiled_bml="$work/bml.lowered.fk"
core_driver="$work/compile-core.fk"

cat > "$core_driver" <<FK
(do
  (form-source-compile-file "form-stdlib/core.fk" "$compiled_core")
  (form-source-compile-file "form-stdlib/compiler.fk" "$compiled_compiler")
  (form-source-compile-file "form-stdlib/grammars/bml.fk" "$compiled_bml"))
FK
(
  cd "$FORM"
  "$GO" \
    form-stdlib/form-ontology-loader.fk \
    form-stdlib/line-grammar.fk \
    form-stdlib/bmf-core.fk \
    form-stdlib/bmf-grammar.fk \
    form-stdlib/bml.fk \
    form-stdlib/bml-source.fk \
    form-stdlib/source-compiler.fk \
    "$core_driver" >/dev/null
)

cat > "$driver" <<'FK'
(defn probe-result-value (m)
    (bmf-object-value (cap-get (match-caps m) "result")))

(defn probe-stream-node (source index)
    (nth
        (bml-source-exec-parse-nodes
            (bml-source-parse-executable-stream
                (bml-source-scan-text source)))
        index))

(defn probe-add-node ()
    (probe-result-value
        (apply-bml-bmf-rule "method-return-add"
            (list (bml-src-name "int") (bml-src-name "Add")
                  (bml-src-op "(") (bml-src-op ")")
                  (bml-src-op "{") (bml-src-keyword "return")
                  (bml-src-int "1") (bml-src-op "+")
                  (bml-src-int "2") (bml-src-op ";")
                  (bml-src-op "}")))))

(defn probe-choose-node ()
    (probe-result-value
        (apply-bml-bmf-rule "choose-fail-int"
            (list (bml-src-keyword "choose") (bml-src-op "{")
                  (bml-src-keyword "fail") (bml-src-op ";") (bml-src-op "}")
                  (bml-src-op ",") (bml-src-op "{")
                  (bml-src-keyword "return") (bml-src-int "8")
                  (bml-src-op ";") (bml-src-op "}")))))

(print "==UNI==")
(print (fkc-emit-universal))
(print "==INT==")
(print (bml-hati-table-file-from-node (probe-stream-node "return 3;\nreturn 1.5;\nreturn 'A';\n" 0)))
(print "==FLOAT==")
(print (bml-hati-table-file-from-node (probe-stream-node "return 3;\nreturn 1.5;\nreturn 'A';\n" 1)))
(print "==CHAR==")
(print (bml-hati-table-file-from-node (probe-stream-node "return 3;\nreturn 1.5;\nreturn 'A';\n" 2)))
(print "==ADD==")
(print (bml-hati-table-file-from-node (probe-add-node)))
(print "==CHOOSE==")
(print (bml-hati-table-file-from-node (probe-choose-node)))
(print "==END==")
FK

(
  cd "$FORM"
  "$GO" \
    "$compiled_core" \
    form-stdlib/minimal-surface.fk \
    form-stdlib/json.fk \
    form-stdlib/cache.fk \
    form-stdlib/form-ontology-loader.fk \
    form-stdlib/engine.fk \
    "$compiled_compiler" \
    form-stdlib/source-compiler.fk \
    form-stdlib/hati-os-kernel.fk \
    form-stdlib/hati-os-kernel-emit.fk \
    "$compiled_bml" \
    "$driver" > "$out"
)

extract_section() {
  local name="$1"
  local target="$2"
  awk -v marker="==$name==" '
    $0 == marker { keep = 1; next }
    keep && /^==.*==$/ { exit }
    keep { print }
  ' "$out" > "$target"
}

universal_c="$work/bml-hati-universal.c"
extract_section "UNI" "$universal_c"
native_bin="$work/bml-hati-universal"
"$CLANG" -O2 -o "$native_bin" "$universal_c"

expected_for() {
  case "$1" in
    INT) echo 3 ;;
    FLOAT) echo 1.5 ;;
    CHAR) echo 0 ;;
    ADD) echo 3 ;;
    CHOOSE) echo 8 ;;
    *) echo "unknown case: $1" >&2; exit 1 ;;
  esac
}

printf 'binary=%s bytes=%s\n' "$native_bin" "$(wc -c < "$native_bin" | tr -d ' ')"
printf 'universal_c_bytes=%s\n' "$(wc -c < "$universal_c" | tr -d ' ')"

run_case() {
  local name="$1"
  local table="$work/$name.table.txt"
  extract_section "$name" "$table"
  python3 - "$native_bin" "$table" "$name" "$(expected_for "$name")" <<'PY'
import statistics
import subprocess
import sys
import time

bin_path, table_path, name, expected = sys.argv[1:5]
samples = []
last = None
for _ in range(11):
    start = time.perf_counter()
    last = subprocess.run([bin_path, table_path, "0"], text=True, capture_output=True, check=False)
    samples.append((time.perf_counter() - start) * 1000.0)
stdout_lines = last.stdout.strip().splitlines()
first = stdout_lines[0].strip() if stdout_lines else ""
stderr = last.stderr.strip()
median_ms = statistics.median(samples)
ok = last.returncode == 0 and not stderr and first == expected
print(
    f"case={name} expected={expected} stdout_first={first} "
    f"stderr={stderr!r} rc={last.returncode} median_ms={median_ms:.3f}"
)
if not ok:
    sys.exit(1)
PY
}

run_case INT
run_case FLOAT
run_case CHAR
run_case ADD
run_case CHOOSE

char_table="$work/CHAR.table.txt"
if ! grep -q "1 1 65" "$char_table"; then
  echo "FAIL: CHAR table does not carry the A literal in the string pool" >&2
  exit 1
fi

echo "char_pool_shape=ok literal=A stdout_is_pool_id=0"

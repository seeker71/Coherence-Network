#!/usr/bin/env bash
# bml_form_jit_metal_planes_audit.sh — supported target assembly floor.
#
# The broad cross-ISA audit can show many experimental organs when the host LLVM
# carries them. This gate is narrower: it follows the supported Hati target
# catalog and proves the two committed metal planes:
#
#   macos-arm64    arm64-apple-macosx      Mach-O relocatable + arm64 assembly
#   android-arm64  aarch64-linux-android   ELF relocatable + aarch64 assembly
#
# Clang is an oracle/sample generator for these lanes. Runtime JIT on Android
# must not depend on clang, so this audit also proves the Form-native arm64
# assembler/lowerer lane before checking clang output.
#
# Both native C surfaces are exercised against the oracle:
#   - BML source -> Hati loadable table -> universal C binary
#   - Form recipe -> jit_emit_c -> target assembly/object
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
GO="$FORM/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"

if ! command -v "$CLANG" >/dev/null 2>&1; then
  echo "FAIL: clang is required for supported metal-plane assembly proof" >&2
  exit 1
fi

if [[ ! -x "$GO" ]]; then
  (cd "$FORM/form-kernel-go" && go build -o bin-go .)
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/bml-form-metal-planes.XXXXXX")"
trap 'rm -rf "$work"' EXIT

native_lane_out="$work/form-native-jit-lanes.out"
(
  cd "$FORM"
  ./validate.sh \
    form-stdlib/core.fk \
    form-stdlib/hati-os-targets.fk \
    form-stdlib/form-asm.fk \
    form-stdlib/form-lower.fk \
    form-stdlib/jit-tensor-emit.fk \
    form-stdlib/tests/jit-metal-lanes-band.fk > "$native_lane_out"
)
if ! grep -q "4095" "$native_lane_out"; then
  cat "$native_lane_out"
  echo "FAIL: Form-native JIT lane proof did not return 4095" >&2
  exit 1
fi
if ! grep -q "fourth arm: 1" "$native_lane_out"; then
  cat "$native_lane_out"
  echo "FAIL: Form-native JIT lane proof did not run four-way on fkwu" >&2
  exit 1
fi
echo "PASS  form-native-jit-lanes: CPU/GPU/ML oracle -> Form-native emitter model -> 4095 four-way"

native_rec_out="$work/form-native-recursive-lowerer.out"
(
  cd "$FORM"
  ./validate.sh \
    form-stdlib/core.fk \
    form-stdlib/form-asm.fk \
    form-stdlib/form-lower.fk \
    form-stdlib/tests/form-lower-rec-band.fk > "$native_rec_out"
)
if ! grep -q "31" "$native_rec_out"; then
  cat "$native_rec_out"
  echo "FAIL: Form-native recursive lowerer proof did not return 31" >&2
  exit 1
fi
if ! grep -q "fourth arm: 1" "$native_rec_out"; then
  cat "$native_rec_out"
  echo "FAIL: Form-native recursive lowerer proof did not run four-way on fkwu" >&2
  exit 1
fi
echo "PASS  form-native-recursive-lowerer: recursive arm64 byte image -> 31 four-way"

oracle_learning_out="$work/jit-oracle-learning.out"
(
  cd "$FORM"
  ./validate.sh \
    form-stdlib/core.fk \
    form-stdlib/tests/jit-oracle-learning-band.fk > "$oracle_learning_out"
)
if ! grep -q "1023" "$oracle_learning_out"; then
  cat "$oracle_learning_out"
  echo "FAIL: JIT oracle learning proof did not return 1023" >&2
  exit 1
fi
if ! grep -q "fourth arm: 1" "$oracle_learning_out"; then
  cat "$oracle_learning_out"
  echo "FAIL: JIT oracle learning proof did not run four-way on fkwu" >&2
  exit 1
fi
echo "PASS  jit-oracle-learning: third-party oracle samples -> measured native choice loop -> 1023 four-way"

driver="$work/emit-surfaces.fk"
out="$work/emit.out"
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
(defn probe-locals-node ()
    (bml-source-exec-parse-node
        (bml-source-parse-executable-stream
            (bml-source-scan-text
                "const int x = 2;\nconst int y = 5;\nreturn x + 1;\n"))))

(print "==BML_UNIVERSAL_C==")
(print (fkc-emit-universal))
(print "==BML_LOCALS_TABLE==")
(print (bml-hati-table-file-from-node (probe-locals-node)))
(print "==FORM_JIT_C==")
(do
    (defn poly (a b)
        (add (mul a a) (mul b b)))
    (print (poly 3 4))
    (print (jit_emit_c "poly")))
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

bml_c="$work/bml-hati-universal.c"
bml_table="$work/bml-locals.table.txt"
form_c_raw="$work/form-jit.raw"
form_c="$work/form-poly.c"
extract_section BML_UNIVERSAL_C "$bml_c"
extract_section BML_LOCALS_TABLE "$bml_table"
extract_section FORM_JIT_C "$form_c_raw"

form_answer="$(sed -n '1p' "$form_c_raw")"
sed '1d' "$form_c_raw" > "$form_c"
if [[ "$form_answer" != "25" ]] || ! grep -q "form_poly" "$form_c"; then
  echo "FAIL: jit_emit_c did not emit form_poly with walker parity answer 25" >&2
  exit 1
fi

if ! grep -q "fk_walk" "$bml_c" || ! grep -q "BML-HATI-UNSUPPORTED" "$bml_table" && ! grep -q " 3 " "$bml_table"; then
  echo "FAIL: BML/Hati surface did not emit universal C plus a loadable locals table" >&2
  exit 1
fi

cat > "$work/form-main.c" <<'EOF'
extern long long form_poly(long long, long long);
int main(void) {
    return form_poly(3, 4) == 25 ? 0 : 1;
}
EOF

"$CLANG" -O2 -o "$work/bml-host" "$bml_c"
bml_host_out="$("$work/bml-host" "$bml_table" 0)"
bml_first="$(printf '%s\n' "$bml_host_out" | sed -n '1p')"
if [[ "$bml_first" != "3" ]]; then
  echo "FAIL: BML/Hati host binary returned '$bml_first' for locals table, expected 3" >&2
  exit 1
fi
echo "PASS  host-bml-hati: locals table stdout_first=3"

"$CLANG" -O2 -o "$work/form-host" "$form_c" "$work/form-main.c"
"$work/form-host"
echo "PASS  host-form-jit: form_poly(3,4)=25"

compile_surface() {
  local plane="$1"
  local triple="$2"
  local file_re="$3"
  local surface="$4"
  local cfile="$5"
  local asm_re="$6"
  local obj="$work/${surface}-${plane}.o"
  local asm="$work/${surface}-${plane}.s"

  "$CLANG" --target="$triple" -O2 -S -o "$asm" "$cfile"
  "$CLANG" --target="$triple" -O2 -c -o "$obj" "$cfile"
  local fdesc
  fdesc="$(file "$obj")"
  local lines
  lines="$(wc -l < "$asm" | tr -d ' ')"

  if ! grep -Eq "$asm_re" "$asm"; then
    echo "FAIL  plane=$plane surface=$surface target=$triple: assembly missing /$asm_re/" >&2
    exit 1
  fi
  if ! grep -Eq "$file_re" <<<"$fdesc"; then
    echo "FAIL  plane=$plane surface=$surface target=$triple: object shape '$fdesc' missing /$file_re/" >&2
    exit 1
  fi

  printf 'PASS  plane=%s surface=%s target=%s asm_lines=%s object=%s\n' \
    "$plane" "$surface" "$triple" "$lines" "$fdesc"
}

compile_surface "macos-arm64" "arm64-apple-macosx" "Mach-O.*arm64" \
  "bml-hati" "$bml_c" "fk_walk|_fk_walk"
compile_surface "macos-arm64" "arm64-apple-macosx" "Mach-O.*arm64" \
  "form-jit" "$form_c" "mul|madd"
compile_surface "android-arm64" "aarch64-linux-android" "ELF 64-bit.*(ARM aarch64|AArch64)" \
  "bml-hati" "$bml_c" "fk_walk|_fk_walk"
compile_surface "android-arm64" "aarch64-linux-android" "ELF 64-bit.*(ARM aarch64|AArch64)" \
  "form-jit" "$form_c" "mul|madd"

echo "ok — Form-native JIT lane proof holds four-way; oracle learning choice floor holds four-way; clang oracle assembly/object receipts cover every supported metal plane"

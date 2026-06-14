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
# Clang is an oracle/sample generator for the broad C surfaces. Runtime JIT on
# Android must not depend on clang, so this audit also proves the Form-native
# arm64 assembler/lowerer lane and Form-native Mach-O/ELF object wrappers before
# checking clang output.
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

native_macho_out="$work/form-native-macho.out"
(
  cd "$FORM"
  ./validate.sh \
    form-stdlib/core.fk \
    form-stdlib/form-asm.fk \
    form-stdlib/form-lower.fk \
    form-stdlib/form-macho.fk \
    form-stdlib/tests/form-macho-band.fk > "$native_macho_out"
)
if ! grep -q "31" "$native_macho_out"; then
  cat "$native_macho_out"
  echo "FAIL: Form-native Mach-O object proof did not return 31" >&2
  exit 1
fi
if ! grep -q "fourth arm: 1" "$native_macho_out"; then
  cat "$native_macho_out"
  echo "FAIL: Form-native Mach-O object proof did not run four-way on fkwu" >&2
  exit 1
fi
echo "PASS  form-native-macho-object: arm64 bytes -> Mach-O relocatable object -> 31 four-way"

native_elf_out="$work/form-native-elf.out"
(
  cd "$FORM"
  ./validate.sh \
    form-stdlib/core.fk \
    form-stdlib/form-asm.fk \
    form-stdlib/form-lower.fk \
    form-stdlib/form-elf.fk \
    form-stdlib/tests/form-elf-band.fk > "$native_elf_out"
)
if ! grep -q "31" "$native_elf_out"; then
  cat "$native_elf_out"
  echo "FAIL: Form-native ELF object proof did not return 31" >&2
  exit 1
fi
if ! grep -q "fourth arm: 1" "$native_elf_out"; then
  cat "$native_elf_out"
  echo "FAIL: Form-native ELF object proof did not run four-way on fkwu" >&2
  exit 1
fi
echo "PASS  form-native-elf-object: arm64 bytes -> ELF64/aarch64 relocatable object -> 31 four-way"

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

jit_lower_gate_out="$work/jit-lower-fourth-arm.out"
(
  cd "$FORM"
  bash scripts/fourth-arm-gate.sh \
    jit-lower \
    jit-lower-program \
    full-jit-lower \
    jit-lower-bmf \
    jit-lower-emit > "$jit_lower_gate_out"
)
for stem in jit-lower jit-lower-program full-jit-lower jit-lower-bmf jit-lower-emit; do
  if ! grep -q "PASS-4WAY  $stem" "$jit_lower_gate_out"; then
    cat "$jit_lower_gate_out"
    echo "FAIL: JIT lower residual cluster did not pass four-way for $stem" >&2
    exit 1
  fi
done
echo "PASS  jit-lower-residuals: logic/fold/unbox/lift/BMF/emit cluster is five-band four-way"

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
(print "==FORM_JIT_LOWERED_C==")
(do
    (let guard-direct (fk-if (fk-le (fk-arg) (fk-lit 10))
                             (fk-le (fk-lit 0) (fk-arg))
                             (fk-lit 0)))
    (print (fkc-emit-many (list (jit-lower-tree guard-direct)))))
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
    form-stdlib/jit-lower.fk \
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
lowered_c="$work/form-jit-lowered.c"
extract_section BML_UNIVERSAL_C "$bml_c"
extract_section BML_LOCALS_TABLE "$bml_table"
extract_section FORM_JIT_C "$form_c_raw"
extract_section FORM_JIT_LOWERED_C "$lowered_c"

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
if ! grep -q "if (t == 70)" "$lowered_c" || ! grep -q "if (t == 79)" "$lowered_c"; then
  echo "FAIL: lowered JIT surface did not emit the reconciled 70..79 lowered lane" >&2
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

"$CLANG" -O2 -o "$work/form-lowered-host" "$lowered_c"
lowered_5="$("$work/form-lowered-host" 5 | sed -n '1p')"
lowered_11="$("$work/form-lowered-host" 11 | sed -n '1p')"
if [[ "$lowered_5" != "1" || "$lowered_11" != "0" ]]; then
  echo "FAIL: lowered JIT host binary returned arg5=$lowered_5 arg11=$lowered_11, expected 1/0" >&2
  exit 1
fi
echo "PASS  host-form-jit-lowered: lowered guard arg5=1 arg11=0"

native_obj_driver="$work/form-native-objects.fk"
native_obj_out="$work/form-native-objects.out"
cat > "$native_obj_driver" <<'FK'
(do
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let prog (list (list 1 40 0 0) (list 1 1 0 0) (list 3 0 1 0) (list 1 1 0 0) (list 4 2 3 0)))
    (let code (lo-compile prog 4))
    (print (str_concat "MACHO_NATIVE " (hxb (mo-object code))))
    (print (str_concat "ELF_NATIVE " (hxb (elf-object code))))
    0)
FK

(
  cd "$FORM"
  "$GO" \
    "$compiled_core" \
    form-stdlib/form-asm.fk \
    form-stdlib/form-lower.fk \
    form-stdlib/form-macho.fk \
    form-stdlib/form-elf.fk \
    "$native_obj_driver" > "$native_obj_out"
)

macho_native_hex="$(grep '^MACHO_NATIVE ' "$native_obj_out" | sed 's/^MACHO_NATIVE //')"
elf_native_hex="$(grep '^ELF_NATIVE ' "$native_obj_out" | sed 's/^ELF_NATIVE //')"
if [[ -z "$macho_native_hex" || -z "$elf_native_hex" ]]; then
  cat "$native_obj_out"
  echo "FAIL: Form-native object emitter did not return Mach-O and ELF hex rows" >&2
  exit 1
fi

macho_native_obj="$work/form-native-macos-arm64.o"
elf_native_obj="$work/form-native-android-arm64.o"
printf '%s' "$macho_native_hex" | xxd -r -p > "$macho_native_obj"
printf '%s' "$elf_native_hex" | xxd -r -p > "$elf_native_obj"
macho_native_desc="$(file "$macho_native_obj")"
elf_native_desc="$(file "$elf_native_obj")"
if ! grep -Eq "Mach-O.*arm64" <<<"$macho_native_desc"; then
  echo "FAIL: Form-native Mach-O object shape '$macho_native_desc' missing Mach-O arm64" >&2
  exit 1
fi
if ! grep -Eq "ELF 64-bit.*(ARM aarch64|AArch64)" <<<"$elf_native_desc"; then
  echo "FAIL: Form-native ELF object shape '$elf_native_desc' missing ELF aarch64" >&2
  exit 1
fi
printf 'PASS  plane=macos-arm64 surface=form-native-object emitter=form-macho object=%s\n' "$macho_native_desc"
printf 'PASS  plane=android-arm64 surface=form-native-object emitter=form-elf object=%s\n' "$elf_native_desc"

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
compile_surface "macos-arm64" "arm64-apple-macosx" "Mach-O.*arm64" \
  "form-jit-lowered" "$lowered_c" "fk_walk|_fk_walk"
compile_surface "android-arm64" "aarch64-linux-android" "ELF 64-bit.*(ARM aarch64|AArch64)" \
  "bml-hati" "$bml_c" "fk_walk|_fk_walk"
compile_surface "android-arm64" "aarch64-linux-android" "ELF 64-bit.*(ARM aarch64|AArch64)" \
  "form-jit" "$form_c" "mul|madd"
compile_surface "android-arm64" "aarch64-linux-android" "ELF 64-bit.*(ARM aarch64|AArch64)" \
  "form-jit-lowered" "$lowered_c" "fk_walk|_fk_walk"

echo "ok — Form-native JIT lane proof holds four-way; Form-native Mach-O/ELF object floors hold four-way; lowered residual cluster holds five-band four-way; oracle learning choice floor holds four-way; clang oracle assembly/object receipts cover every supported metal plane including lowered JIT"

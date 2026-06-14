#!/usr/bin/env bash
# bml_form_jit_metal_planes_audit.sh — supported target assembly floor.
#
# The broad cross-ISA audit can show many experimental organs when the host LLVM
# carries them. This gate is narrower: it follows the supported Hati target
# catalog and proves the two committed metal planes:
#
#   macos-arm64    arm64-apple-macosx      Mach-O relocatable + arm64 assembly
#   android-arm64  aarch64-linux-android   ELF relocatable/executable + aarch64 assembly
#
# Clang is an oracle/sample generator for the broad C surfaces. Runtime JIT on
# Android must not depend on clang, so this audit also proves the Form-native
# arm64 assembler/lowerer lane, Form-native Mach-O/ELF object wrappers, and the
# Form-native Android ELF executable shape before checking clang output.
#
# Android execution runner selection:
#   FORM_ELF_EXEC_REQUIRE_ANDROID=1  require an authorized adb arm64 device
#   FORM_ELF_EXEC_ADB_SERIAL=<id>    select one adb device when several are live
#   FORM_ELF_EXEC_RUNNER=<command>   force a qemu-like command runner
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

native_elf_exec_out="$work/form-native-elf-exec.out"
(
  cd "$FORM"
  ./validate.sh \
    form-stdlib/core.fk \
    form-stdlib/form-elf-exec.fk \
    form-stdlib/tests/form-elf-exec-band.fk > "$native_elf_exec_out"
)
if ! grep -q "63" "$native_elf_exec_out"; then
  cat "$native_elf_exec_out"
  echo "FAIL: Form-native ELF executable proof did not return 63" >&2
  exit 1
fi
if ! grep -q "fourth arm: 1" "$native_elf_exec_out"; then
  cat "$native_elf_exec_out"
  echo "FAIL: Form-native ELF executable proof did not run four-way on fkwu" >&2
  exit 1
fi
echo "PASS  form-native-elf-executable: _start write+exit bytes -> ELF64/aarch64 executable -> 63 four-way"

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
    (print (str_concat "ELF_EXEC_NATIVE " (hxb (elf-exec (elf-exec-write-exit-code (list 70 79 82 77 32 69 76 70 10) 42)))))
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
    form-stdlib/form-elf-exec.fk \
    "$native_obj_driver" > "$native_obj_out"
)

macho_native_hex="$(grep '^MACHO_NATIVE ' "$native_obj_out" | sed 's/^MACHO_NATIVE //')"
elf_native_hex="$(grep '^ELF_NATIVE ' "$native_obj_out" | sed 's/^ELF_NATIVE //')"
elf_exec_native_hex="$(grep '^ELF_EXEC_NATIVE ' "$native_obj_out" | sed 's/^ELF_EXEC_NATIVE //')"
if [[ -z "$macho_native_hex" || -z "$elf_native_hex" || -z "$elf_exec_native_hex" ]]; then
  cat "$native_obj_out"
  echo "FAIL: Form-native emitter did not return Mach-O object, ELF object, and ELF executable hex rows" >&2
  exit 1
fi

macho_native_obj="$work/form-native-macos-arm64.o"
elf_native_obj="$work/form-native-android-arm64.o"
elf_exec_native="$work/form-native-android-arm64.elf"
printf '%s' "$macho_native_hex" | xxd -r -p > "$macho_native_obj"
printf '%s' "$elf_native_hex" | xxd -r -p > "$elf_native_obj"
printf '%s' "$elf_exec_native_hex" | xxd -r -p > "$elf_exec_native"
chmod +x "$elf_exec_native"
macho_native_desc="$(file "$macho_native_obj")"
elf_native_desc="$(file "$elf_native_obj")"
elf_exec_native_desc="$(file "$elf_exec_native")"
if ! grep -Eq "Mach-O.*arm64" <<<"$macho_native_desc"; then
  echo "FAIL: Form-native Mach-O object shape '$macho_native_desc' missing Mach-O arm64" >&2
  exit 1
fi
if ! grep -Eq "ELF 64-bit.*(ARM aarch64|AArch64)" <<<"$elf_native_desc"; then
  echo "FAIL: Form-native ELF object shape '$elf_native_desc' missing ELF aarch64" >&2
  exit 1
fi
if ! grep -Eq "ELF 64-bit.*executable.*(ARM aarch64|AArch64)" <<<"$elf_exec_native_desc"; then
  echo "FAIL: Form-native ELF executable shape '$elf_exec_native_desc' missing ELF executable aarch64" >&2
  exit 1
fi
printf 'PASS  plane=macos-arm64 surface=form-native-object emitter=form-macho object=%s\n' "$macho_native_desc"
printf 'PASS  plane=android-arm64 surface=form-native-object emitter=form-elf object=%s\n' "$elf_native_desc"
printf 'PASS  plane=android-arm64 surface=form-native-executable emitter=form-elf-exec executable=%s\n' "$elf_exec_native_desc"

elf_exec_runner="${FORM_ELF_EXEC_RUNNER:-}"
elf_exec_runner_kind=""
elf_exec_docker_image="${FORM_ELF_EXEC_DOCKER_IMAGE:-alpine:3.20}"
elf_exec_adb_serial="${FORM_ELF_EXEC_ADB_SERIAL:-}"
elf_exec_adb_selected=""
elf_exec_adb_reason=""
elf_exec_skip_reason="runner=qemu-aarch64 unavailable; executable shape inspected"

select_adb_device() {
  elf_exec_adb_selected=""
  elf_exec_adb_reason=""
  if ! command -v adb >/dev/null 2>&1; then
    elf_exec_adb_reason="adb unavailable"
    return 1
  fi
  if [[ -n "$elf_exec_adb_serial" ]]; then
    local state
    state="$(adb -s "$elf_exec_adb_serial" get-state 2>/dev/null || true)"
    if [[ "$state" == "device" ]]; then
      elf_exec_adb_selected="$elf_exec_adb_serial"
      return 0
    fi
    elf_exec_adb_reason="adb serial=$elf_exec_adb_serial state=${state:-missing}"
    return 1
  fi

  local devices
  devices="$(adb devices | awk 'NR > 1 && $2 == "device" { print $1 }')"
  local count
  count="$(printf '%s\n' "$devices" | sed '/^$/d' | wc -l | tr -d ' ')"
  if [[ "$count" == "1" ]]; then
    elf_exec_adb_selected="$(printf '%s\n' "$devices" | sed -n '1p')"
    return 0
  fi
  if [[ "$count" == "0" ]]; then
    elf_exec_adb_reason="adb has no authorized device"
  else
    elf_exec_adb_reason="adb has $count authorized devices; set FORM_ELF_EXEC_ADB_SERIAL"
  fi
  return 1
}

mask_adb_serial() {
  local serial="$1"
  local len="${#serial}"
  if (( len <= 4 )); then
    printf '****'
  else
    printf '****%s' "${serial: -4}"
  fi
}

elf_exec_adb_requested=0
if [[ "${FORM_ELF_EXEC_ADB:-0}" == "1" || "${FORM_ELF_EXEC_REQUIRE_ANDROID:-0}" == "1" || "$elf_exec_runner" == "adb" || "$elf_exec_runner" == "android-adb" ]]; then
  elf_exec_adb_requested=1
fi

if [[ "$elf_exec_adb_requested" == "1" ]]; then
  if select_adb_device; then
    elf_exec_runner_kind="adb"
    elf_exec_runner="adb"
  else
    echo "FAIL: Form-native ELF executable requested Android adb runner but $elf_exec_adb_reason" >&2
    exit 1
  fi
elif [[ -n "$elf_exec_runner" ]]; then
  elf_exec_runner_kind="command"
elif select_adb_device; then
  elf_exec_runner_kind="adb"
  elf_exec_runner="adb"
else
  elf_exec_runner="$(command -v qemu-aarch64 || command -v qemu-aarch64-static || true)"
  if [[ -n "$elf_exec_runner" ]]; then
    elf_exec_runner_kind="command"
  elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    if [[ "${FORM_ELF_EXEC_DOCKER_PULL:-0}" == "1" ]] || docker image inspect "$elf_exec_docker_image" >/dev/null 2>&1; then
      elf_exec_runner_kind="docker"
      elf_exec_runner="docker"
    else
      elf_exec_skip_reason="runner=qemu-aarch64 unavailable; docker image=$elf_exec_docker_image missing (set FORM_ELF_EXEC_DOCKER_PULL=1 to pull); executable shape inspected"
    fi
  else
    elf_exec_skip_reason="runner=qemu-aarch64 unavailable; docker unavailable; executable shape inspected"
  fi
fi
if [[ "$elf_exec_runner_kind" == "command" ]]; then
  set +e
  elf_exec_stdout="$("$elf_exec_runner" "$elf_exec_native" 2>"$work/form-native-elf-exec.stderr")"
  elf_exec_rc=$?
  set -e
  elf_exec_stderr="$(cat "$work/form-native-elf-exec.stderr")"
  if [[ "$elf_exec_rc" -ne 42 || "$elf_exec_stdout" != "FORM ELF" || -n "$elf_exec_stderr" ]]; then
    echo "FAIL: Form-native ELF executable runner=$elf_exec_runner rc=$elf_exec_rc stdout='$elf_exec_stdout' stderr='$elf_exec_stderr'" >&2
    exit 1
  fi
  echo "PASS  plane=android-arm64 surface=form-native-executable runner=$elf_exec_runner stdout='FORM ELF' stderr='' exit=42"
elif [[ "$elf_exec_runner_kind" == "adb" ]]; then
  elf_exec_model="$(adb -s "$elf_exec_adb_selected" shell getprop ro.product.model | tr -d '\r')"
  elf_exec_android="$(adb -s "$elf_exec_adb_selected" shell getprop ro.build.version.release | tr -d '\r')"
  elf_exec_abi="$(adb -s "$elf_exec_adb_selected" shell getprop ro.product.cpu.abi | tr -d '\r')"
  if ! grep -q "arm64" <<<"$elf_exec_abi"; then
    echo "FAIL: Form-native ELF executable adb device abi='$elf_exec_abi' is not arm64" >&2
    exit 1
  fi
  elf_exec_remote="/data/local/tmp/form-native-android-arm64-$$.elf"
  elf_exec_remote_stdout="/data/local/tmp/form-native-android-arm64-$$.stdout"
  elf_exec_remote_stderr="/data/local/tmp/form-native-android-arm64-$$.stderr"
  elf_exec_remote_rc="/data/local/tmp/form-native-android-arm64-$$.rc"
  adb -s "$elf_exec_adb_selected" push "$elf_exec_native" "$elf_exec_remote" >/dev/null 2>&1
  adb -s "$elf_exec_adb_selected" shell "chmod 755 '$elf_exec_remote'"
  adb -s "$elf_exec_adb_selected" shell "rm -f '$elf_exec_remote_stdout' '$elf_exec_remote_stderr' '$elf_exec_remote_rc'; '$elf_exec_remote' >'$elf_exec_remote_stdout' 2>'$elf_exec_remote_stderr'; echo \$? >'$elf_exec_remote_rc'" >/dev/null
  elf_exec_stdout="$(adb -s "$elf_exec_adb_selected" shell "cat '$elf_exec_remote_stdout' 2>/dev/null" | tr -d '\r')"
  elf_exec_stderr="$(adb -s "$elf_exec_adb_selected" shell "cat '$elf_exec_remote_stderr' 2>/dev/null" | tr -d '\r')"
  elf_exec_rc="$(adb -s "$elf_exec_adb_selected" shell "cat '$elf_exec_remote_rc' 2>/dev/null" | tr -d '\r[:space:]')"
  adb -s "$elf_exec_adb_selected" shell "rm -f '$elf_exec_remote' '$elf_exec_remote_stdout' '$elf_exec_remote_stderr' '$elf_exec_remote_rc'" >/dev/null || true
  if [[ "$elf_exec_rc" != "42" || "$elf_exec_stdout" != "FORM ELF" || -n "$elf_exec_stderr" ]]; then
    echo "FAIL: Form-native ELF executable runner=adb device=$(mask_adb_serial "$elf_exec_adb_selected") rc=$elf_exec_rc stdout='$elf_exec_stdout' stderr='$elf_exec_stderr'" >&2
    exit 1
  fi
  echo "PASS  plane=android-arm64 surface=form-native-executable runner=adb device=$(mask_adb_serial "$elf_exec_adb_selected") model='$elf_exec_model' android=$elf_exec_android abi=$elf_exec_abi stdout='FORM ELF' stderr='' exit=42"
elif [[ "$elf_exec_runner_kind" == "docker" ]]; then
  set +e
  elf_exec_stdout="$(docker run --rm --platform linux/arm64 -v "$work:/work:ro" "$elf_exec_docker_image" "/work/$(basename "$elf_exec_native")" 2>"$work/form-native-elf-exec.stderr")"
  elf_exec_rc=$?
  set -e
  elf_exec_stderr="$(cat "$work/form-native-elf-exec.stderr")"
  if [[ "$elf_exec_rc" -ne 42 || "$elf_exec_stdout" != "FORM ELF" || -n "$elf_exec_stderr" ]]; then
    echo "FAIL: Form-native ELF executable runner=docker image=$elf_exec_docker_image rc=$elf_exec_rc stdout='$elf_exec_stdout' stderr='$elf_exec_stderr'" >&2
    exit 1
  fi
  echo "PASS  plane=android-arm64 surface=form-native-executable runner=docker-linux-arm64 image=$elf_exec_docker_image stdout='FORM ELF' stderr='' exit=42"
else
  echo "SKIP  plane=android-arm64 surface=form-native-executable $elf_exec_skip_reason"
fi

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

echo "ok — Form-native JIT lane proof holds four-way; Form-native Mach-O/ELF object floors and Android ELF executable shape hold four-way; Android ELF execution receipt runs through adb/qemu/Docker when a live runner is available; lowered residual cluster holds five-band four-way; oracle learning choice floor holds four-way; clang oracle assembly/object receipts cover every supported metal plane including lowered JIT"

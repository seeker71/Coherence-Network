#!/usr/bin/env bash
# form_cli_slice.sh — compile a Form recipe slice to a RUNNABLE native binary,
# content-address it, and ledger it as a native-recipe crossing. Zero clang.
#
# This is the deepest surface of the membrane: a native binary stays fully in the
# Form body — no oracle, no interpreter. The Form recipes lower an op-tagged tree
# to arm64 machine code (form-lower.fk), wrap it in a Mach-O object (form-macho.fk
# on macOS) or ELF (form-elf-exec.fk on Linux/Android); ld links it; the binary
# RUNS and its exit code IS the program's value. The binary's sha256 is its
# content address — the stable identity the substrate interns as an ARTIFACT cell
# (BDomain.ARTIFACT=16) with a NodeID, so it is addressable "for anyone".
#
# The slice spec is the LOWERED IR — op-tagged nodes (tag c1 c2 c3), the same
# shape form-lower walks. Tags: 1=LIT(value in slot1) 2=ARG 3=ADD 4=SUB 3-cond.
# (A recipe -> IR front-end is a separate cell; the lowered subset is small and
# this proves the spec->binary->address->ledger arc end to end.)
#
# Usage: form_cli_slice.sh [name] [prog-tree] [root-index] [expected-exit]
# Default slice: ((40 + 2)) = 42.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; STD="$FORM/form-stdlib"
NAME="${1:-answer}"
PROG="${2:-(list (list 1 40 0 0) (list 1 2 0 0) (list 3 0 1 0))}"
ROOTI="${3:-2}"
EXPECT="${4:-42}"
[[ -x "$GO" ]] || ( cd "$FORM/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

echo "── form-cli native slice: $NAME (program root $ROOTI, expect $EXPECT) ──"

OS="$(uname -s)"; ARCH="$(uname -m)"
work="$(mktemp -d "${TMPDIR:-/tmp}/fslice.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# 1. Form: lower the tree -> native object bytes (hex). No clang. -------------
emit_macho() {
    { sed '$ d' "$STD/form-asm.fk"
      sed '1,/^(do$/d;$ d' "$STD/form-lower.fk"
      sed '1,/^(do$/d;$ d' "$STD/form-macho.fk"
      cat <<DRV
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let prog $PROG)
    (print (str_concat "SLICE " (hxb (mo-object (lo-compile prog $ROOTI)))))
    0)
DRV
    } > "$work/d.fk"
    ( cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null ) | grep '^SLICE ' | sed 's/^SLICE //'
}

if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
    hex="$(emit_macho)"
    [[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; exit 1; }
    echo "$hex" | xxd -r -p > "$work/$NAME.o"
    echo "[1] Form-emitted Mach-O object: $(wc -c < "$work/$NAME.o" | tr -d ' ') bytes (no clang)"
    SDK="$(xcrun --show-sdk-path 2>/dev/null)"
    ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/$NAME" "$work/$NAME.o" 2>/dev/null
    "$work/$NAME"; rc=$?
    BIN="$work/$NAME"
    if [[ "$rc" == "$EXPECT" ]]; then
        echo "[2] native binary RAN — exit code $rc = the program's value ✓ (zero clang)"
    else
        echo "[2] FAIL: expected exit $EXPECT, got $rc"; exit 1
    fi
else
    echo "[1] macOS/arm64 slice path; on $OS/$ARCH the ELF path (form-elf-exec.fk) builds the object —"
    echo "    Android arm64 device execution is proven separately (form-elf-exec-band 63, adb receipt)."
    exit 0
fi

# 2. Content address: the sha256 IS the substrate identity --------------------
SHA="$(shasum -a 256 "$BIN" | awk '{print $1}')"
echo "[3] content address (sha256): $SHA"
echo "    addressable as ARTIFACT cell (BDomain.ARTIFACT=16); the substrate interns"
echo "    a NodeID on ingest — auto on merge via scripts/substrate_post_merge_hook.sh,"
echo "    or: python3 scripts/coh_substrate.py ingest <path-to-slice>"

# 3. Ledger the slice as a native-recipe crossing (it stayed in the body) -----
led="$work/led.fk"
{ cat "$STD/core-native.fk"
  cat "$STD/tool-channel.fk" "$STD/choice-receipt.fk" "$STD/form-cli-membrane.fk"
  echo "(let cx (fcm-crossing \"slice:$NAME\" \"cap.compute.native\" (fcm-surface-native) 1 \"native binary slice sha256 $SHA\" \"success\" 100 0))"
  echo '(print (fcm-surface-crossed? (fcm-x-surface cx)))'
  echo '(print (fcm-crossing-valid? cx "form-cli" "form_cli_slice" 20260616))'
} > "$led"
L_CROSSED=""; L_VALID=""; i=0
while IFS= read -r line; do
    line="$(printf '%s' "$line" | tr -d '[:space:]')"
    [[ -z "$line" || "$line" == "null" ]] && continue
    case $i in 0) L_CROSSED="$line";; 1) L_VALID="$line";; esac; i=$((i+1))
done < <("$GO" "$led" 2>/dev/null)
echo "[4] ledger crossing: surface=native-recipe os-membrane-crossed=$L_CROSSED receipt-valid=$L_VALID"
echo "── slice '$NAME' built, ran, addressed, and ledgered — fully in the body, offline."

#!/usr/bin/env bash
# jit_assembly_audit.sh — read the JIT's machine code and measure the gap.
#
# The value-parity bands prove the JIT computes the right ANSWER; this
# instrument proves it emits the SHAPE we expect, by disassembling the
# actual .so the Go arm builds from a Form recipe and reading the
# instructions. Two horizons, both explicit:
#
#   MINIMUM (today's contract — gates, nonzero exit on failure):
#     M0  value parity: the compiled recipe returns the walker's answer
#     M1  the plugin exports the compiled symbol (nm)
#     M2  arithmetic resolves INSIDE the plugin: jitabi.Mul/Sub are
#         native code in the same .so, and a machine multiply (imul)
#         exists in that native body — no hop back into the kernel for
#         a pure-int recipe
#     M3  the recursion is a real native call, not an interpreter loop
#
#   NORTH STAR (measured, reported, never gated — the gap is the point):
#     N1  hot-function instructions       target <= 32   (a tight int64
#         recursive fact is ~16 instructions)
#     N2  boxed-value traffic (movups)    target  = 0    (de-boxed ABI
#         has no 80-byte Value copies)
#     N3  stack frame bytes               target <= 64
#     N4  helper calls in the hot body    target  = 0    (imul inlined
#         into the hot body itself, not reached through jitabi.Mul)
#
# The gap report is the verification: when a JIT improvement lands, this
# audit shows the numbers moving toward the north star, and the minimum
# gates keep "native" honest while they move.
#
# Run:  scripts/jit_assembly_audit.sh            # audit the fact recipe
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

# ── 1. compile the probe recipe through the kernel's own JIT door ──
driver="$(mktemp "${TMPDIR:-/tmp}/jit-asm-driver.XXXXXX.fk")"
trap 'rm -f "$driver"' EXIT
cat > "$driver" <<'EOF'
(do
    (defn fact (n)
        (if (le n 1) 1
            (mul n (fact (sub n 1)))))
    (let compiled (jit_compile "fact"))
    (print compiled)
    (print (fact 10))
    0)
EOF
out="$(cd "$FORMDIR" && "$GO_BIN" "$driver" 2>/dev/null)"
compiled="$(printf '%s\n' "$out" | sed -n 1p)"
answer="$(printf '%s\n' "$out" | sed -n 2p)"

if [[ "$compiled" != "1" ]]; then
    echo "FAIL  M0: jit_compile(fact) returned '$compiled' (expected 1)"; exit 1
fi
if [[ "$answer" != "3628800" ]]; then
    echo "FAIL  M0: fact(10) returned '$answer' (expected 3628800) — value parity broken"; exit 1
fi
echo "PASS  M0: value parity: jit_compile=1, fact(10)=3628800"

# newest plugin whose generated source names the fact closure
plugdir="$(grep -l 'Closure name: fact' /tmp/form-jit-*/main.go 2>/dev/null \
            | xargs -r ls -td 2>/dev/null | head -1 | xargs -r dirname)"
so="$plugdir/plugin.so"
if [[ -z "$plugdir" || ! -f "$so" ]]; then
    echo "FAIL  M1: no fact plugin.so found under /tmp/form-jit-*"; exit 1
fi

# ── 2. disassemble the hot function ──
sym="$(nm -D --defined-only "$so" | awk '/ T .*\.fn_value$/{print $3; exit}')"
if [[ -z "$sym" ]]; then
    echo "FAIL  M1: compiled symbol fn_value not exported by $so"; exit 1
fi
echo "PASS  M1: symbol exported: $sym"
full="$(objdump -d --no-show-raw-insn "$so")"
asm="$(awk -v s="<${sym}>:" 'index($0,s){f=1;next} f&&/^$/{exit} f{print}' <<<"$full")"
mulasm="$(awk '/<form-kernel-go\/jitabi.Mul>:/{f=1;next} f&&/^$/{exit} f{print}' <<<"$full")"

# ── 3. minimum gates ──
fails=0
hotcalls="$(grep 'call' <<<"$asm" || true)"
foreign="$(grep -v 'jitabi\.\|fn_value\|runtime\.' <<<"$hotcalls" || true)"
if grep -q 'imul' <<<"$mulasm" && [[ -z "$foreign" ]]; then
    echo "PASS  M2: arithmetic is native inside the plugin (imul in jitabi.Mul; no foreign hops)"
else
    echo "FAIL  M2: arithmetic leaves the plugin or has no machine multiply"
    [[ -n "$foreign" ]] && printf '      foreign calls:\n%s\n' "$foreign"
    fails=1
fi
if grep -q "call.*fn_value" <<<"$asm"; then
    echo "PASS  M3: recursion is a native call into the compiled body"
else
    echo "FAIL  M3: no native self-call — recursion may be interpreted"; fails=1
fi

# ── 4. north-star metrics — the measured gap ──
insns=$(grep -cE '^[[:space:]]+[0-9a-f]+:' <<<"$asm" || true)
boxmoves=$(grep -cE 'movups|movdqu' <<<"$asm" || true)
frame=$(grep -oE 'sub +\$0x[0-9a-f]+,%rsp' <<<"$asm" | head -1 | grep -oE '0x[0-9a-f]+' || echo 0x0)
frame_dec=$((frame))
helpercalls=$(grep -c 'call.*jitabi\.' <<<"$asm" || true)
inline_imul=$(grep -c 'imul' <<<"$asm" || true)

echo ""
echo "north-star gap (fact, hot function):"
printf '  N1 instructions        %6s   target <= 32\n'  "$insns"
printf '  N2 boxed-value moves   %6s   target  = 0\n'   "$boxmoves"
printf '  N3 stack frame bytes   %6s   target <= 64\n'  "$frame_dec"
printf '  N4 helper calls        %6s   target  = 0  (inline imul in hot body: %s)\n' "$helpercalls" "$inline_imul"
echo "  plugin: $so"
echo ""
if [[ $fails -eq 0 ]]; then
    echo "MINIMUM met. The gap above is the distance to the de-boxed, inlined north star."
else
    echo "MINIMUM NOT met — the JIT is not emitting what we expect."
fi
exit $fails

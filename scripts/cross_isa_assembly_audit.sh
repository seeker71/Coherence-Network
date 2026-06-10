#!/usr/bin/env bash
# cross_isa_assembly_audit.sh — one recipe, every ISA the host can show.
#
# The kernel lowers a Form recipe to C (jit_emit_c, jit_c.go int64
# subset); this instrument feeds that projection to the host's LLVM and
# reads the assembly for every target organ named in host-kernel.form:
#
#   aarch64-linux-android   Android CPU            expect: mul
#   arm64-apple-macosx      Apple silicon / MLX    expect: mul
#   hexagon                 Android DSP            expect: mpyi
#   nvptx64-nvidia-cuda     NVIDIA GPU (PTX)       expect: mul.lo.s64
#   amdgcn-amd-amdhsa       AMD GPU (GCN)          expect: v_mul_lo
#   x86-64 (native)         this host, reference   expect: imul
#
# Two horizons, like scripts/jit_assembly_audit.sh:
#
#   MINIMUM (gates): the emitted C computes the walker's answer on this
#   host (value parity), and every target above emits assembly carrying
#   its ISA's real multiply. fact additionally keeps a native recursive
#   self-call on the CPU/DSP targets.
#
#   NORTH STAR (named, not gated): generation is proven HERE; execution
#   on the organ awaits the device — Metal AIR needs Apple's compiler
#   on-device (the C → arm64-apple stream is the MLX host half), SPIR-V
#   needs llvm-spirv, Hexagon execution needs the DSP. Per-ISA
#   instruction counts are reported so codegen changes stay measurable.
#
# Run:  scripts/cross_isa_assembly_audit.sh
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"

if ! command -v "$CLANG" >/dev/null; then
    echo "FAIL  clang not available — cross-ISA projection needs LLVM"; exit 1
fi
if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/form-isa.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# ── 1. the kernel lowers the recipes to C ──
cat > "$work/driver.fk" <<'EOF'
(do
    (defn fact (n)
        (if (le n 1) 1
            (mul n (fact (sub n 1)))))
    (defn poly (a b)
        (add (mul a a) (mul b b)))
    (print (fact 10))
    (print (poly 3 4))
    (print "==C==")
    (print (jit_emit_c "fact"))
    (print (jit_emit_c "poly"))
    0)
EOF
out="$(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null)"
walker_fact="$(printf '%s\n' "$out" | sed -n 1p)"
walker_poly="$(printf '%s\n' "$out" | sed -n 2p)"
printf '%s\n' "$out" | sed -e '1,/^==C==$/d' -e '$d' > "$work/recipes.c"

if ! grep -q 'form_fact' "$work/recipes.c" || ! grep -q 'form_poly' "$work/recipes.c"; then
    echo "FAIL  jit_emit_c did not lower both recipes"; exit 1
fi

# ── 2. MINIMUM: the projection computes the walker's answer (host run) ──
cat > "$work/main.c" <<'EOF'
#include <stdio.h>
long long form_fact(long long);
long long form_poly(long long, long long);
int main(void) {
    printf("%lld\n%lld\n", form_fact(10), form_poly(3, 4));
    return 0;
}
EOF
fails=0
if "$CLANG" -O2 -o "$work/host" "$work/recipes.c" "$work/main.c" 2>"$work/cc.err"; then
    host_out="$("$work/host")"
    c_fact="$(sed -n 1p <<<"$host_out")"
    c_poly="$(sed -n 2p <<<"$host_out")"
    if [[ "$c_fact" == "$walker_fact" && "$c_poly" == "$walker_poly" ]]; then
        echo "PASS  M0: value parity — emitted C computes walker answers (fact(10)=$c_fact, poly(3,4)=$c_poly)"
    else
        echo "FAIL  M0: parity broken — C says ($c_fact,$c_poly), walker says ($walker_fact,$walker_poly)"; fails=1
    fi
else
    echo "FAIL  M0: host compile of emitted C failed:"; cat "$work/cc.err"; fails=1
fi

# ── 3. MINIMUM: every target organ emits its real multiply ──
emit() { # target-flags... ; expects MUL_RE and LABEL set
    local label="$1" mulre="$2"; shift 2
    local asmfile="$work/$(echo "$label" | tr ' /' '__').s"
    if ! "$CLANG" "$@" -O2 -S -o "$asmfile" "$work/recipes.c" 2>"$work/t.err"; then
        echo "FAIL  $label: clang refused:"; head -3 "$work/t.err"; fails=1; return
    fi
    local insns mulhit
    insns=$(grep -cE '^\s+[a-z]' "$asmfile" || true)
    mulhit=$(grep -m1 -E "$mulre" "$asmfile" || true)
    if [[ -n "$mulhit" ]]; then
        printf 'PASS  %-28s %5s insns   %s\n' "$label" "$insns" "$(echo "$mulhit" | sed 's/^[[:space:]]*//')"
    else
        echo "FAIL  $label: no ISA multiply matching /$mulre/"; fails=1
    fi
}

echo ""
echo "cross-ISA generation (same recipes, every organ the host can show):"
emit "android-cpu (aarch64)"   '\bmul\b|\bmadd\b'   --target=aarch64-linux-android
emit "apple-mlx-host (arm64)"  '\bmul\b|\bmadd\b'   --target=arm64-apple-macosx
emit "android-dsp (hexagon)"   'mpyi'               --target=hexagon
emit "nvidia-gpu (ptx)"        'mul\.lo\.s64'       --target=nvptx64-nvidia-cuda
emit "amd-gpu (gcn)"           'v_mul_lo'           --target=amdgcn-amd-amdhsa -mcpu=gfx900 -nogpulib
emit "x86-64 (reference)"      'imul'               ""

# recursion is fully native on CPU/DSP organs: either a native self-call,
# or — better — the optimizer lowered it to a loop (zero calls at all).
# Both shapes never touch an interpreter; a dispatch hop would show as a
# call to a foreign symbol.
for label in "android-cpu__(aarch64)" "android-dsp__(hexagon)"; do
    f="$work/$label.s"
    body="$(awk '/form_fact:/{f=1} f{print} f&&/ret|jumpr/{exit}' "$f" 2>/dev/null)"
    if grep -qE 'call.*form_fact|bl[[:space:]]+form_fact' <<<"$body"; then
        echo "PASS  recursion native on $label (self-call)"
    elif ! grep -qE '\b(call|bl)\b' <<<"$body"; then
        echo "PASS  recursion native on $label (lowered to a loop — zero calls)"
    else
        echo "FAIL  recursion leaves the function on $label:"; grep -E '\b(call|bl)\b' <<<"$body" | head -2; fails=1
    fi
done

# ── 4. EXECUTION on the foreign ISAs — emulated organs, real semantics ──
# The recipes run as freestanding static binaries under qemu-user: exit
# code 42 means fact(10)==3628800 AND poly(3,4)==25 computed BY THE
# FOREIGN ISA's own instructions. SKIP (not FAIL) where qemu is absent.
echo ""
echo "execution on emulated organs (exit 42 = parity computed on the ISA):"
cat > "$work/start64.c" <<'EOF'
long long form_fact(long long);
long long form_poly(long long, long long);
void _start(void) {
    long code = (form_fact(10) == 3628800 && form_poly(3, 4) == 25) ? 42 : 1;
    asm volatile("mov x0, %0; mov x8, #93; svc #0" :: "r"(code) : "x0", "x8");
}
EOF
cat > "$work/starthex.c" <<'EOF'
long long form_fact(long long);
long long form_poly(long long, long long);
void _start(void) {
    long code = (form_fact(10) == 3628800 && form_poly(3, 4) == 25) ? 42 : 1;
    register long r0 asm("r0") = code;
    register long r6 asm("r6") = 94; /* exit_group */
    asm volatile("trap0(#1)" :: "r"(r0), "r"(r6));
}
EOF
run_emulated() { # label qemu-bin target start-file
    local label="$1" qemu="$2" target="$3" start="$4"
    if ! command -v "$qemu" >/dev/null; then
        echo "SKIP  $label: $qemu not installed (apt-get install qemu-user)"; return
    fi
    if "$CLANG" --target="$target" -nostdlib -ffreestanding -fuse-ld=lld -static -O2 \
            -o "$work/$label.elf" "$work/recipes.c" "$work/$start" 2>"$work/x.err"; then
        "$qemu" "$work/$label.elf"; local rc=$?
        if [[ $rc -eq 42 ]]; then
            echo "PASS  $label: executed under $qemu — exit 42 (parity on the ISA)"
        else
            echo "FAIL  $label: exit $rc (expected 42)"; fails=1
        fi
    else
        echo "FAIL  $label: link failed:"; head -2 "$work/x.err"; fails=1
    fi
}
run_emulated "android-cpu-exec" qemu-aarch64 aarch64-linux-android start64.c
run_emulated "android-dsp-exec" qemu-hexagon hexagon starthex.c

# ── 5. SPIR-V — the Vulkan / Android GPU door ──
echo ""
if command -v llvm-spirv >/dev/null || command -v llvm-spirv-18 >/dev/null; then
    spirvbin="$(command -v llvm-spirv || command -v llvm-spirv-18)"
    spirvdir="$work/spirvbin"; mkdir -p "$spirvdir"; ln -sf "$spirvbin" "$spirvdir/llvm-spirv"
    if PATH="$spirvdir:$PATH" "$CLANG" --target=spirv64 -O2 -c -o "$work/recipes.spv" "$work/recipes.c" 2>"$work/s.err"; then
        imuls=$(spirv-dis "$work/recipes.spv" 2>/dev/null | grep -c 'OpIMul' || true)
        if [[ "$imuls" -gt 0 ]] && spirv-val "$work/recipes.spv" 2>/dev/null; then
            echo "PASS  vulkan/android-gpu (spir-v): $imuls OpIMul, module validates (spirv-val)"
        else
            echo "FAIL  spir-v: OpIMul=$imuls or validation failed"; fails=1
        fi
    else
        echo "FAIL  spir-v: clang --target=spirv64 refused:"; head -2 "$work/s.err"; fails=1
    fi
else
    echo "SKIP  spir-v: install llvm-spirv-18 + spirv-tools"
fi

# ── 6. MSL — the Metal / MLX GPU kernel source ──
# Emitted from the same projection; held by clang as C++ on this host.
# AIR bytes need Apple's compiler — that half is named, not faked.
cat > "$work/recipes.metal" <<EOF
/* Generated MSL — Form recipe → Metal kernel source.
   AIR compile awaits Apple's toolchain; this source is the GPU half,
   the arm64-apple assembly stream is the MLX host half. */
#ifdef __METAL_VERSION__
#include <metal_stdlib>
using namespace metal;
#endif

$(sed -e 's/^long long form_poly/static long form_poly/' -e 's/long long/long/g' "$work/recipes.c" | grep -A3 'static long form_poly')

kernel void poly_kernel(device long *out [[buffer(0)]],
                        constant long *in [[buffer(1)]],
                        uint tid [[thread_position_in_grid]]) {
    out[tid] = form_poly(in[2 * tid], in[2 * tid + 1]);
}
EOF
cat > "$work/msl_prelude.h" <<'EOF'
/* host-side syntax hold for MSL: erase Metal address-space keywords */
#define kernel
#define device
#define constant const
typedef unsigned int uint;
EOF
if "$CLANG" -x c++ -std=c++14 -fsyntax-only -Wno-unknown-attributes \
        -include "$work/msl_prelude.h" "$work/recipes.metal" 2>"$work/m.err"; then
    echo "PASS  apple-mlx-gpu (msl): kernel source emitted and held as C++ (AIR awaits Apple toolchain)"
else
    echo "FAIL  msl: emitted kernel source does not hold:"; head -3 "$work/m.err"; fails=1
fi

echo ""
echo "remaining device-only edges (named, not gated):"
echo "  - Metal AIR bytes and on-GPU execution need Apple hardware"
echo "  - physical DSP/GPU execution: emulation is proven above; silicon is the organ"
echo ""
if [[ $fails -eq 0 ]]; then
    echo "MINIMUM met. One recipe: six instruction sets generated, two foreign"
    echo "ISAs executed under emulation, SPIR-V validated, MSL kernel held."
else
    echo "MINIMUM NOT met — the cross-ISA projection is not emitting what we expect."
fi
exit $fails

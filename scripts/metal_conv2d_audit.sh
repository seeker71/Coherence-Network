#!/usr/bin/env bash
# metal_conv2d_audit.sh — GPU witness for conv2d on the real Apple GPU. The Metal mirror of the
# PTX conv2d proof (scripts/.. / form_cuda_ptx_conv2d_host.c): a hand-authored MSL kernel
# (form/native/metal/conv2d.metal) that walks cv2d-conv's EXACT nested right-fold (ky↓ kx↓ ic↓,
# nested td/wd/acc accumulators, + bias), compiled mathMode=.safe (IEEE, no fast-math contraction
# so the mul/add pair never fuses to an FMA), gated BIT-EXACT (uint32-identical) against the same
# CPU oracle and the same deterministic seeds as the CUDA host. A shape counts only when EVERY
# output element matches to the last bit. conv2d is the diffusion/vision stem (form-stdlib/conv2d.fk).
#
# The MSL is a hand-authored carrier today, at parity with the PTX side (template_conv2d.ptx is also
# hand-authored, not yet in the form-ptx emitter band); Form-emitting the MSL (a jte-conv2d-msl
# recipe, like jte-matvec-msl) is the next lift on both lanes.
#
# Carriers: Metal.framework + swiftc (the driver-organ idiom, host-kernel.form host-resource-access).
# No third-party deps. Run:  scripts/metal_conv2d_audit.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MDIR="$ROOT/form/native/metal"
HOST_SRC="$MDIR/form_metal_conv2d_host.swift"
KERNEL="$MDIR/conv2d.metal"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain on this host — the GPU witness needs an Apple GPU + swiftc"
    exit 2
fi
if [[ ! -f "$KERNEL" || ! -f "$HOST_SRC" ]]; then
    echo "FAIL  missing $KERNEL or $HOST_SRC"; exit 1
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/fkmetalconv.XXXXXX")"
trap 'rm -rf "$work"' EXIT
BIN="$work/form_metal_conv2d_host"
swiftc -O -o "$BIN" "$HOST_SRC" 2>"$work/swiftc.err" || {
    echo "FAIL  swiftc could not build the conv2d witness host:"; cat "$work/swiftc.err"; exit 1; }

# Shapes exercising pad {0,1,2}, stride {1,2,3}, 1x1/3x3/4x4/5x5 kernels, asymmetric H/W, varied channels.
overall=0
device=""
echo "witness conv2d (Apple GPU, bit-exact uint32 vs cv2d-conv / form_cuda_ptx_conv2d_host.c oracle):"
while read -r ic oc h w kh kw pad stride; do
    [[ -z "$ic" ]] && continue
    out="$("$BIN" "$KERNEL" "$ic" "$oc" "$h" "$w" "$kh" "$kw" "$pad" "$stride" 2>&1)"
    [[ -z "$device" ]] && device="$(printf '%s\n' "$out" | sed -n 's/^device=//p')"
    kl="$(printf '%s\n' "$out" | sed -n 's/^kernel=form_conv2d_f32  //p')"
    pl="$(printf '%s\n' "$out" | sed -n 's/^parity_//p')"
    if printf '%s\n' "$out" | grep -q '^ok'; then
        echo "  PASS  $kl  |  parity_$pl"
    else
        echo "  FAIL  IC=$ic OC=$oc ${h}x${w} k${kh}x${kw} pad${pad} stride${stride}"
        printf '%s\n' "$out" | sed 's/^/        /'; overall=1
    fi
done <<'EOF'
2 3 5 5 3 3 1 1
3 4 7 7 3 3 1 1
2 3 8 8 3 3 0 1
1 1 6 6 3 3 1 2
4 2 9 9 5 5 2 1
3 5 16 16 3 3 1 2
2 8 12 10 4 4 1 3
6 6 5 5 1 1 0 1
EOF

echo
echo "conditions: $(uname -m) $(uname -s) $(sw_vers -productVersion 2>/dev/null), device=${device:-?}," \
     "Metal runtime compile (makeLibrary, mathMode=safe — IEEE, no fast-math), one thread per output" \
     "element, CPU oracle = cv2d-conv's nested ky↓kx↓ic↓ fold (two-rounding mul/add, zero-pad skip)," \
     "bit-exact gate = uint32-identical, no tolerance"
if [[ "$overall" != "0" ]]; then exit 1; fi
echo "ok — conv2d is bit-exact on the Apple GPU across pad/stride/kernel/shape; the diffusion stem runs on Metal"

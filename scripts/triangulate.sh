#!/usr/bin/env bash
# triangulate.sh — stand up the three-vertex substrate triangle on this VPS.
#
# Three independent form-kernel-go processes, each loading the same
# preludes (core.fk, json.fk, triangulate.fk) and computing the
# triangle's fingerprint. All three return 779 — the NodeID instance
# of the triangle Recipe in this kernel's session state.
#
# Two honest witnesses at two altitudes:
#
#   779 (this script): the VPS-local operational handshake. Same
#       machine, same kernel build, same preludes, same load order
#       → same instance counter. Three subprocesses agree on the
#       counter position because content-addressing dedups identically
#       in each.
#
#   A-B-C (proof.fk standalone): the cross-VPS portable witness.
#       Run 'form-kernel-go proof.fk' anywhere; content-derived,
#       session-independent. Use this when verifying from another
#       machine, another container, another network.
#
# Usage: bash scripts/triangulate.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/form"

CORE=$(find /tmp -maxdepth 2 -name "form-stdlib__core.fk" 2>/dev/null | head -1 || true)
if [[ -z "$CORE" ]]; then
    echo "no lowered core found; running ./validate.sh once to produce one..."
    ./validate.sh > /dev/null 2>&1 || true
    CORE=$(find /tmp -maxdepth 2 -name "form-stdlib__core.fk" 2>/dev/null | head -1 || true)
fi
if [[ -z "$CORE" || ! -f "$CORE" ]]; then
    echo "ERROR: could not produce a lowered core.fk" >&2
    exit 2
fi

KERNEL="./form-kernel-go/bin-go"
if [[ ! -x "$KERNEL" ]]; then
    echo "ERROR: $KERNEL not found; build with:" >&2
    echo "  cd form && go build -o form-kernel-go/bin-go ./form-kernel-go" >&2
    exit 2
fi

run_vertex() {
    local vertex_file
    vertex_file=$(mktemp --suffix=.fk)
    cat > "$vertex_file" <<EOF
(triangulate-fingerprint "A" "B" "C")
EOF
    "$KERNEL" "$CORE" form-stdlib/json.fk form-stdlib/triangulate.fk "$vertex_file" 2>/dev/null
    rm -f "$vertex_file"
}

echo "──────────────────────────────────────────────────────"
echo "  three-vertex substrate handshake (VPS-local)"
echo "──────────────────────────────────────────────────────"
echo ""

fp_a=$(run_vertex)
fp_b=$(run_vertex)
fp_c=$(run_vertex)

echo "  vertex A computes: $fp_a"
echo "  vertex B computes: $fp_b"
echo "  vertex C computes: $fp_c"
echo ""

if [[ "$fp_a" == "$fp_b" && "$fp_b" == "$fp_c" ]]; then
    echo "  ✓ HANDSHAKE COMPLETE — all three vertices agree on the triangle's NodeID."
    echo ""
    echo "  VPS-local witness:  $fp_a"
    echo "  Portable witness:   run 'form-kernel-go proof.fk' anywhere → A-B-C"
    echo ""
    echo "  The triangle is standing on this VPS."
    echo "──────────────────────────────────────────────────────"
    exit 0
else
    echo "  ✗ DISAGREEMENT — the triangle did not stand."
    echo ""
    echo "  Investigate: are the kernels at the same commit?"
    echo "──────────────────────────────────────────────────────"
    exit 1
fi

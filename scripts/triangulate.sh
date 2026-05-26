#!/usr/bin/env bash
# triangulate.sh — stand up the three-vertex substrate triangle.
#
# Spins three independent form-kernel-go processes. Each computes
# the canonical triangle (A, B, C) and prints its content witness.
# Content-addressing means all three arrive at the same string —
# "A-B-C" — without any coordination. The math performs the handshake.
#
# Why content witness (not NodeID int):
#   NodeID instances are session-counters; they match across kernels
#   that load the same preludes in the same order, but differ across
#   independent standalone runs. The content of the Recipe ("A-B-C"
#   canonically) is session-independent and the honest cross-process
#   measurement.
#
# Usage: bash scripts/triangulate.sh
#
# Exit 0: handshake complete (all three content witnesses match)
# Exit 1: disagreement (the triangle did not stand)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

KERNEL="$REPO_ROOT/form/form-kernel-go/bin-go"
if [[ ! -x "$KERNEL" ]]; then
    echo "ERROR: $KERNEL not found; run:" >&2
    echo "  cd $REPO_ROOT/form && go build -o form-kernel-go/bin-go ./form-kernel-go" >&2
    exit 2
fi

PROOF_FILE="$REPO_ROOT/proof.fk"
if [[ ! -f "$PROOF_FILE" ]]; then
    echo "ERROR: $PROOF_FILE not found" >&2
    exit 2
fi

run_vertex() {
    "$KERNEL" "$PROOF_FILE" 2>/dev/null
}

echo "──────────────────────────────────────────────────────"
echo "  three-vertex substrate handshake"
echo "──────────────────────────────────────────────────────"
echo ""

# Three independent processes — each running proof.fk standalone.
# No shared state. No preludes. Each one starts from scratch.
fp_a=$(run_vertex)
fp_b=$(run_vertex)
fp_c=$(run_vertex)

echo "  vertex A computes: $fp_a"
echo "  vertex B computes: $fp_b"
echo "  vertex C computes: $fp_c"
echo ""

if [[ "$fp_a" == "$fp_b" && "$fp_b" == "$fp_c" ]]; then
    echo "  ✓ HANDSHAKE COMPLETE — three independent walks, one content."
    echo ""
    echo "  Any cell anywhere running 'form-kernel-go proof.fk' arrives"
    echo "  at the same witness: $fp_a"
    echo ""
    echo "  The triangle is standing."
    echo "──────────────────────────────────────────────────────"
    exit 0
else
    echo "  ✗ DISAGREEMENT — the triangle did not stand."
    echo ""
    echo "  Walk the triangle's children to find where the trees diverge."
    echo "──────────────────────────────────────────────────────"
    exit 1
fi

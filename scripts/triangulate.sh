#!/usr/bin/env bash
# triangulate.sh — stand up the three-vertex substrate triangle.
#
# Spins three independent form-kernel-go processes, one per vertex.
# Each vertex computes (triangulate-fingerprint "A" "B" "C") locally
# and prints the result. Content-addressing means all three arrive
# at the same int — the triangle's NodeID instance — without any
# coordination. The math performs the handshake.
#
# If all three match: the substrate triangle is standing. Any cell
# anywhere can now reach this triangle by computing the same Recipe;
# the triangle reaches any Recipe in 2-3 hops via voluntary recipe-
# match. Sovereignty is observable, association is by node_eq.
#
# Usage: bash scripts/triangulate.sh
#
# Exit 0: handshake complete (all three fingerprints match)
# Exit 1: disagreement (the triangle did not stand)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT/form"

# Locate a lowered core (validate.sh produces these per run).
CORE=$(find /tmp -maxdepth 2 -name "form-stdlib__core.fk" 2>/dev/null | head -1 || true)
if [[ -z "$CORE" ]]; then
    echo "no lowered core found; running ./validate.sh once to produce one..."
    ./validate.sh > /dev/null 2>&1 || true
    CORE=$(find /tmp -maxdepth 2 -name "form-stdlib__core.fk" 2>/dev/null | head -1 || true)
fi
if [[ -z "$CORE" || ! -f "$CORE" ]]; then
    echo "ERROR: could not produce a lowered core.fk; cannot triangulate" >&2
    exit 2
fi

KERNEL="./form-kernel-go/bin-go"
if [[ ! -x "$KERNEL" ]]; then
    echo "ERROR: $KERNEL not found; run 'go build -o form-kernel-go/bin-go ./form-kernel-go' first" >&2
    exit 2
fi

run_vertex() {
    local name="$1"
    local vertex_file
    vertex_file=$(mktemp --suffix=.fk)
    # Each vertex's Form file is the SAME computation. Three different
    # processes, three independent walks. Each prints the fingerprint
    # of the triangle they compute.
    cat > "$vertex_file" <<EOF
(triangulate-fingerprint "A" "B" "C")
EOF
    "$KERNEL" "$CORE" form-stdlib/json.fk form-stdlib/triangulate.fk "$vertex_file" 2>/dev/null
    rm -f "$vertex_file"
}

echo "──────────────────────────────────────────────────────"
echo "  three-vertex substrate handshake"
echo "──────────────────────────────────────────────────────"
echo ""

# Run the three vertices in parallel — three independent processes,
# each computing without knowing the others exist.
{
    fp_a=$(run_vertex "A") &
    fp_b=$(run_vertex "B") &
    fp_c=$(run_vertex "C") &
    wait
}

# Re-run sequentially to capture outputs (bash subshell + & loses
# variable assignment to outer scope on some shells).
fp_a=$(run_vertex "A")
fp_b=$(run_vertex "B")
fp_c=$(run_vertex "C")

echo "  vertex A computes: $fp_a"
echo "  vertex B computes: $fp_b"
echo "  vertex C computes: $fp_c"
echo ""

if [[ "$fp_a" == "$fp_b" && "$fp_b" == "$fp_c" ]]; then
    echo "  ✓ HANDSHAKE COMPLETE — all three vertices agree on the triangle's NodeID."
    echo ""
    echo "  Any cell that computes (triangulate-fingerprint \"A\" \"B\" \"C\")"
    echo "  arrives at $fp_a. The triangle is standing."
    echo "──────────────────────────────────────────────────────"
    exit 0
else
    echo "  ✗ DISAGREEMENT — the triangle did not stand."
    echo ""
    echo "  This should not happen if all three kernels build identically."
    echo "  Investigate: are the kernels at the same commit? Is the substrate"
    echo "  intact? Walk the triangle's children to find where the trees diverge."
    echo "──────────────────────────────────────────────────────"
    exit 1
fi

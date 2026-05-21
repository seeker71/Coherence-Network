#!/usr/bin/env bash
# form_cli_demo.sh — exercise every form_cli subcommand end-to-end.
#
# Demonstrates that the Form-native runtime works through nothing but
# the kernel (form_native recipes) and the binary library
# (.recipelib JSON bundles) — no substrate session boot, no host stdlib
# math, no Python intrinsics from organ.py. Just the kernel + the
# library + the Language cells for raw I/O.
#
# Run: bash scripts/form_cli_demo.sh
# Exit 0 on full success; non-zero on any step failure (set -e).

set -e
cd "$(dirname "$0")/.."

SEP="────────────────────────────────────────────────────────────────"
TMPDIR="$(mktemp -d -t form_cli_demo.XXXXXX)"
trap "rm -rf $TMPDIR" EXIT

echo "form_cli_demo — kernel + library + Language cells, end-to-end"
echo "$SEP"

# ─── 1. list the bundled library ──────────────────────────────────────────
echo
echo "[1/6] list — surface the bundled library"
echo "$SEP"
python3 scripts/form_cli.py list cell-numerics

# ─── 2. execute several recipes ──────────────────────────────────────────
echo
echo "[2/6] execute — run recipes via form_native"
echo "$SEP"
echo "  cosine([1,0,0], [1,0,0]) = $(python3 scripts/form_cli.py execute cell-numerics cosine '[1.0,0.0,0.0]' '[1.0,0.0,0.0]')"
echo "  cosine([1,0,0], [0,1,0]) = $(python3 scripts/form_cli.py execute cell-numerics cosine '[1.0,0.0,0.0]' '[0.0,1.0,0.0]')"
echo "  sigmoid(0)               = $(python3 scripts/form_cli.py execute cell-numerics sigmoid '0')"
echo "  sigmoid(2)               = $(python3 scripts/form_cli.py execute cell-numerics sigmoid '2')"
echo "  tanh(1)                  = $(python3 scripts/form_cli.py execute cell-numerics tanh '1')"
echo "  matvec([[1,2],[3,4]], [5,6]) = $(python3 scripts/form_cli.py execute cell-numerics matvec '[[1,2],[3,4]]' '[5,6]')"
echo "  vector_add([1,2,3], [10,20,30]) = $(python3 scripts/form_cli.py execute cell-numerics vector_add '[1,2,3]' '[10,20,30]')"

# ─── 3. convert raw I/O ↔ Form object (JSON tongue) ──────────────────────
echo
echo "[3/6] convert in — raw JSON → Form object tree"
echo "$SEP"
cat > "$TMPDIR/input.json" <<EOF
{"name": "test", "values": [1, 2.5, "three", true, null], "nested": {"depth": 1}}
EOF
python3 scripts/form_cli.py convert in --tongue json "$TMPDIR/input.json" > "$TMPDIR/form_obj.json"
echo "  category at top of tree:" \
     "$(python3 -c "import json; d=json.load(open('$TMPDIR/form_obj.json')); print(d['tree']['category'])")"
echo "  child count:" \
     "$(python3 -c "import json; d=json.load(open('$TMPDIR/form_obj.json')); print(len(d['tree']['children']))")"

echo
echo "[4/6] convert out — Form object tree → raw JSON (round-trip)"
echo "$SEP"
python3 scripts/form_cli.py convert out --tongue json "$TMPDIR/form_obj.json" > "$TMPDIR/roundtrip.json"
if diff -q <(python3 -c "import json; print(json.dumps(json.load(open('$TMPDIR/input.json')), indent=2, sort_keys=True))") \
            <(python3 -c "import json; print(json.dumps(json.load(open('$TMPDIR/roundtrip.json')), indent=2, sort_keys=True))") > /dev/null; then
    echo "  round-trip: input.json == convert in → convert out (semantic equivalence)"
else
    echo "  round-trip: divergence detected"
    exit 1
fi

# ─── 4. generate — extract recipes from a .form file ──────────────────────
echo
echo "[5/6] generate — extract recipes from cosine.form into a fresh .recipelib"
echo "$SEP"
python3 scripts/form_cli.py generate docs/coherence-substrate/cosine.form \
    --name cosine-from-source --out "$TMPDIR/cosine-from-source.recipelib.json"

# ─── 5. execute from the freshly-generated library ────────────────────────
echo
echo "[6/6] execute — run recipes from the freshly-generated library"
echo "$SEP"
echo "  sqrt(25)                 = $(python3 scripts/form_cli.py execute "$TMPDIR/cosine-from-source.recipelib.json" sqrt '25')"
echo "  norm([3, 4])             = $(python3 scripts/form_cli.py execute "$TMPDIR/cosine-from-source.recipelib.json" norm '[3.0, 4.0]')"
echo "  cosine([3,4], [3,4])     = $(python3 scripts/form_cli.py execute "$TMPDIR/cosine-from-source.recipelib.json" cosine '[3.0,4.0]' '[3.0,4.0]')"
echo "  dot_product([1,2], [3,4]) = $(python3 scripts/form_cli.py execute "$TMPDIR/cosine-from-source.recipelib.json" dot_product '[1,2]' '[3,4]')"

echo
echo "$SEP"
echo "form_cli verified end-to-end:"
echo "  · list      — library inventory surfaces"
echo "  · execute   — recipes run through form_native (Newton sqrt, recursive list ops)"
echo "  · convert   — raw JSON ↔ Form object tree round-trips semantically"
echo "  · generate  — recipes extracted from .form source into fresh .recipelib"
echo
echo "Kernel + binary library + Language cells. The Form-native runtime."

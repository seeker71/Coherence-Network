#!/usr/bin/env bash
# bmf_bootstrap_audit.sh — measure the BMF bootstrap's minimum closure vs releasable tissue.
#
# Emits the self-contained bootstrap .fkb (the 8 source-compile preludes bundled), then
# walks it with form-stdlib/reachability.fk from the REAL entry points and tiers every
# defn:
#   FLOOR      — reached from the compile entry (fsc-compile-section-recipe): the minimum
#                to compile ANY BMF/BML section (parse + emit).
#   STORE      — reached from setup/runtime entries but not the compile entry (the ontology
#                load, the runtime the emitted recipe needs). FLOOR + STORE = must-store.
#   RELEASABLE — reached from NO entry: candidate old bootstrap tissue to compost.
#
# This is the instrument for releasing old tissue toward a north-star streaming compiler:
# it turns "release some of that" into an exact, regenerable list. The walk is STATIC
# (FNCALL/IDENT refs); a defn reached only via a CONSTRUCTED name looks RELEASABLE but is
# not — verify dynamic refs per-defn before composting.
#
# Run:  scripts/bmf_bootstrap_audit.sh            # summary + tier counts
#       scripts/bmf_bootstrap_audit.sh --names    # also print every defn, tagged by tier
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
RS_BIN="$FORMDIR/form-kernel-rust/target/release/form-kernel-rust"
RC="$FORMDIR/form-stdlib/reachability.fk"
PRELUDES=(json cache form-ontology-loader line-grammar bmf-core bmf-grammar bml source-compiler)
WANT_NAMES=0
[[ "${1:-}" == "--names" ]] && WANT_NAMES=1

if [[ ! -x "$RS_BIN" || "$FORMDIR/form-kernel-rust/src/main.rs" -nt "$RS_BIN" ]]; then
    echo "  building rust kernel..." >&2
    (cd "$FORMDIR/form-kernel-rust" && cargo build --release --quiet)
fi

cd "$FORMDIR"
prelude_args=()
for p in "${PRELUDES[@]}"; do prelude_args+=("form-stdlib/$p.fk"); done

fkb="$(mktemp "${TMPDIR:-/tmp}/bmf-bootstrap.XXXXXX.fkb")"
trap 'rm -f "$fkb" "$drv"' EXIT
"$RS_BIN" --emit-binary "$fkb" "${prelude_args[@]}" >/dev/null

drv="$(mktemp "${TMPDIR:-/tmp}/bmf-audit-drv.XXXXXX.fk")"
cat > "$drv" <<EOF
(do
  (let program (read_form_binary "$fkb"))
  (let pairs (rc-pairs program (empty)))
  (let all-defns (rc-names pairs (empty)))
  (let floor (reachable-from program "fsc-compile-section-recipe"))
  (let entries (rc-append (rc-toplevel program (empty))
                  (list "fsc-compile-section-recipe" "form-bmf-second" "bmf-section" "form-source-compile-file")))
  (let store (rc-reach entries pairs (empty)))
  (defn tag (name) (if (rc-member? name store) (if (rc-member? name floor) "FLOOR" "STORE") "RELEASABLE"))
  (defn dump (names) (if (rc-empty? names) 0 (do (print (str_concat (str_concat (tag (head names)) "\t") (head names))) (dump (tail names)))))
  (dump all-defns))
EOF

tsv="$("$RS_BIN" "$RC" "$drv" 2>/dev/null | grep -E '^(FLOOR|STORE|RELEASABLE)	')"
floor=$(printf '%s\n' "$tsv" | grep -c '^FLOOR')
store=$(printf '%s\n' "$tsv" | grep -c '^STORE')
rel=$(printf '%s\n' "$tsv" | grep -c '^RELEASABLE')
total=$((floor + store + rel))

echo "BMF bootstrap closure audit"
echo "  total defns:        $total"
echo "  FLOOR (compile min): $floor"
echo "  STORE (setup+runtime): $store   -> must-store: $((floor + store))"
echo "  RELEASABLE (candidate compost): $rel"

if [[ "$WANT_NAMES" -eq 1 ]]; then
    echo; printf '%s\n' "$tsv" | sort
fi

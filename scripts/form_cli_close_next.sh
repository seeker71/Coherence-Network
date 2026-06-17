#!/usr/bin/env bash
# form_cli_close_next.sh — the autonomous self-closer, FOUR-WAY gated.
#
# One iteration: find the next open gap -> a LOCAL oracle drafts the recipe ->
# the kernel validates it (Go) -> form_cli_prove4 proves it FOUR-WAY (Go/Rust/TS +
# the 4th kernel fkwu, 0 divergent) -> only then is it LOADED native (a proven
# stdlib cell the next iteration preludes). A recipe that drafts and Go-validates
# but does NOT cross fkwu is NOT loaded — Go-only is not native. Run again to
# advance; a blocker stops the loop and names itself. 0 remote oracle calls.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"
CN="$HOME/.coherence-network/close-next"; mkdir -p "$CN"
CLOSED="$CN/closed.txt"; touch "$CLOSED"
LOADED="$CN/loaded.txt"; touch "$LOADED"   # proven recipe basenames, accumulating native
ORACLE="${1:-ollama run coder}"

# the gap queue — fine closable units (the ll-buffer memory model, decomposed).
queue() { cat <<'Q'
ll-alloc16|(alloc16) returns the byte image for 'sub sp, sp, #16' by calling (fa-sub-x-imm 31 31 16). Output ONLY the recipe.|(fa-conviction (alloc16) (list 255 67 0 209))|1
ll-store-w8|(store-w8) returns the byte image for 'str w8, [sp, #8]' by calling (fa-str-w 8 31 8). Output ONLY the recipe.|(fa-conviction (store-w8) (list 232 11 0 185))|1
ll-load-w9|(load-w9) returns the byte image for 'ldr w9, [sp, #12]' by calling (fa-ldr-w 9 31 12). Output ONLY the recipe.|(fa-conviction (load-w9) (list 233 15 64 185))|1
ll-free16|(free16) returns the byte image for 'add sp, sp, #16' by calling (fa-add-x-imm 31 31 16). Output ONLY the recipe.|(fa-conviction (free16) (list 255 67 0 145))|1
Q
}

next=""
while IFS='|' read -r id spec assert expected; do
    [ -z "${id:-}" ] && continue
    grep -qx "$id" "$CLOSED" && continue
    next="$id|$spec|$assert|$expected"; break
done <<< "$(queue)"
[ -n "$next" ] || { echo "── close-next: queue drained. $(grep -c . "$CLOSED") features loaded native (four-way). ──"; exit 0; }
IFS='|' read -r id spec assert expected <<< "$next"

prelude="form-asm.fk $(tr '\n' ' ' < "$LOADED")"
echo "── close-next: '$id'  (loaded native so far: $(grep -c . "$CLOSED"); prelude: $prelude) ──"

# 1. draft + Go-validate
bash "$ROOT/scripts/form_cli_close_gap.sh" "$id" "$spec" "$assert" "$expected" "$ORACLE" "$prelude" 2>&1 | tee "$CN/last.out" | sed -n '2,4p'
grep -q 'CLOSED offline' "$CN/last.out" || { echo "── '$id' did not draft/Go-validate. Blocker above. ──"; exit 1; }

# 2. FOUR-WAY gate — incl. the 4th kernel fkwu. Go-only does not load.
echo "  [4-way gate] proving '$id' across Go/Rust/TS/fkwu …"
if bash "$ROOT/scripts/form_cli_prove4.sh" "$id" "$assert" "$expected" "$prelude"; then
    echo "$id" >> "$CLOSED"; echo "$id.fk" >> "$LOADED"
    echo "── '$id' LOADED native (FOUR-WAY incl. fkwu). $(grep -c . "$CLOSED") features, 0 remote. Run again. ──"
    exit 0
else
    echo "── '$id' drafted + Go-validated but did NOT cross the 4th kernel — NOT loaded. Fix the blocker. ──"
    exit 1
fi

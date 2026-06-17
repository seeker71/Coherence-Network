#!/usr/bin/env bash
# form_cli_close_next.sh — the autonomous self-closer, one iteration of the flywheel.
#
# Find the next open gap -> learn its shape -> a LOCAL oracle drafts the recipe ->
# the kernel validates it -> on success, make it AVAILABLE NATIVE for the next
# iteration by appending the validated recipe to the loaded ledger that the next
# close preludes. Run it in a loop (form-cli close-next, again, again) and the body
# grows one native feature at a time, offline, with no remote oracle. When a gap
# does NOT close, the loop stops and names the blocker — that is the issue to fix
# before the next pass (the walk-and-fix rhythm).
#
# The loaded ledger ($STD/.cache/close-next-loaded.fk, gitignored) is the growing
# set of closed recipes the next iteration can call — "the new feature available
# native to run the next iteration." Hot closures JIT to a .so transparently.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"
CN="$HOME/.coherence-network/close-next"; mkdir -p "$CN" "$STD/.cache"
LOADED="$STD/.cache/close-next-loaded.fk"; [ -f "$LOADED" ] || : > "$LOADED"
CLOSED="$CN/closed.txt"; touch "$CLOSED"
ORACLE="${1:-ollama run coder}"

# The gap queue — fine, closable units (the ll-buffer memory model, decomposed).
# id | recipe-spec | assert-expr | expected. Each builds on form-asm + what's loaded.
queue() { cat <<'Q'
ll-alloc16|(alloc16) returns the byte image for the arm64 instruction 'sub sp, sp, #16' by calling (fa-sub-x-imm 31 31 16). Output ONLY the recipe.|(fa-conviction (alloc16) (list 255 67 0 209))|1
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

if [ -z "$next" ]; then
    echo "── close-next: queue drained. $(grep -c . "$CLOSED") features loaded native. ──"
    echo "   add the next gaps to the queue (the composed buffer round-trip uses these), or extend form-lower's dispatch."
    exit 0
fi

IFS='|' read -r id spec assert expected <<< "$next"
echo "── close-next iteration: gap '$id'  (loaded so far: $(grep -c . "$CLOSED")) ──"
echo "  prelude (native features available): form-asm.fk + $(grep -c '(defn' "$LOADED" 2>/dev/null || echo 0) closed recipes"

bash "$ROOT/scripts/form_cli_close_gap.sh" "$id" "$spec" "$assert" "$expected" "$ORACLE" "form-asm.fk .cache/close-next-loaded.fk" 2>&1 | tee "$CN/last.out" | sed -n '2,8p'

if grep -q 'CLOSED offline' "$CN/last.out"; then
    cat "$STD/drafts/$id.fk" >> "$LOADED"
    grep -qx "$id" "$CLOSED" || echo "$id" >> "$CLOSED"
    echo "── '$id' LOADED native → available to the next iteration ($(grep -c . "$CLOSED") features, 0 remote calls). Run again. ──"
    exit 0
else
    echo "── '$id' did NOT close. The blocker above is the issue to fix before the next pass. ──"
    exit 1
fi

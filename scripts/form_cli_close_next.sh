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

# the gap queue — hand-seeded closable units (id|spec|assert|expected). The
# ll-buffer memory model closed through this loop and now lives composed + four-way
# in form-stdlib/ll-buffer.fk (ll-alloc(n)/ll-store(rt,off)/ll-load/ll-free + ll-buf);
# its four atomic leaves are superseded by that model, not requeued. The hand-seed
# is the bootstrap proof that the loop works end-to-end; the next rung is autonomous
# gap-finding — the loop sourcing open gaps from form-cli-gaps.fk rather than this
# literal list.
queue() { cat <<'Q'
Q
}

next=""
while IFS='|' read -r id spec assert expected; do
    [ -z "${id:-}" ] && continue
    grep -qx "$id" "$CLOSED" && continue
    next="$id|$spec|$assert|$expected"; break
done <<< "$(queue)"
[ -n "$next" ] || { echo "── close-next: hand-seed drained. $(grep -c . "$CLOSED") features loaded native (four-way, 0 remote). Next rung: autonomous gap-finding from form-cli-gaps.fk. ──"; exit 0; }
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

#!/usr/bin/env bash
# form_debug_demo.sh — LIVE DEBUGGING: the value trace joined with provenance.
# The debug walker emits (node, value, depth) per completed node; provenance maps
# each node to its source file:line:col — so the trace reads as a SOURCE-LEVEL
# step log of the running binary, and a watchpoint shows every value one source
# line produced, in execution order. Replay is free: the walker is deterministic.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fdbg.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# the original source (provenance points back here)
cat > "$work/fib-source.fk" <<'EOF'
; fib-source.fk — the source under live debugging
(let fibc
  (fk-if (fk-le (fk-arg) (fk-lit 1))
         (fk-arg)
         (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1)))
                 (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
EOF

# emit the DEBUG walker, compile, run fib(5) with the trace on (limit 200)
cat "$FORM/form-stdlib/minimal-surface.fk" "$FORM/form-stdlib/fourth-walker.fk" \
    "$FORM/form-stdlib/fourth-walker-emit.fk" "$work/fib-source.fk" > "$work/e.fk"
printf '(print "==C==")\n(print (fkc-emit-debug (list fibc)))\n(print "==END==")\n' >> "$work/e.fk"
(cd "$FORM" && "$GO" "$work/e.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/dbg.c"
"$CLANG" -O2 -o "$work/dbg" "$work/dbg.c"

"$work/dbg" 5 200 > "$work/trace.txt"
val="$(grep -v '^E ' "$work/trace.txt" | head -1)"
nev="$(grep -c '^E ' "$work/trace.txt")"
echo "running binary: fib(5) = $val — $nev (node, value, depth) events traced live"
echo "clean-run check: $( "$work/dbg" 5 | wc -l | tr -d ' ' ) line(s) with trace off (the value only)"

# provenance: node -> line:col of the original source
src_escaped="$(python3 -c 'import sys,json; print(json.dumps(open(sys.argv[1]).read()))' "$work/fib-source.fk")"
{ cat "$FORM/form-stdlib/form-provenance.fk"; cat <<DRV
(do
    (let src $src_escaped)
    (let locs (fp-locate src))
    (defn em (i) (print (str_concat (int_to_str (fp-line src (nth locs i))) (str_concat ":" (int_to_str (fp-col src (nth locs i)))))))
    (defn ems2 (a i) (ems i))
    (defn ems (i) (if (eq i (len locs)) 0 (ems2 (em i) (add i 1))))
    (print "LOCS") (ems 0) 0)
DRV
} > "$work/loc.fk"
locs=(); first=0
while IFS= read -r l; do
    [[ "$l" == "LOCS" ]] && first=1 && continue
    [[ "$first" == 1 && "$l" != "0" ]] && locs+=("$l")
done < <(cd "$FORM" && "$GO" "$work/loc.fk" 2>/dev/null)

echo
echo "the step log — first 14 events, each joined to its source line (the live debugger):"
echo "  step  node  value  depth  source"
i=0
grep '^E ' "$work/trace.txt" | head -14 | while read -r _ node value depth; do
    i=$((i+1)); lc="${locs[$node]:-?}"; line="${lc%%:*}"
    srcline="$(sed -n "${line}p" "$work/fib-source.fk" | sed 's/^[[:space:]]*//' | cut -c1-44)"
    printf "  %-5s %-5s %-6s %-6s fib-source.fk:%-5s %s\n" "$i" "$node" "$value" "$depth" "$lc" "$srcline"
done

# the WATCHPOINT: every value the (fk-sub ... 1) site produced, in order
echo
subnode=6   # row 6 = the first SUB site (verified by the provenance table)
watch="$(grep '^E ' "$work/trace.txt" | awk -v n=$subnode '$2==n {printf "%s ", $3}')"
maxd="$(grep '^E ' "$work/trace.txt" | awk 'BEGIN{m=0} {if ($4>m) m=$4} END{print m}')"
echo "WATCH fib-source.fk:${locs[$subnode]} (fk-sub (fk-arg) (fk-lit 1)) -> values in order: $watch"
echo "deepest stack reached: $maxd  (the recursion's true depth, observed not inferred)"
echo
echo "LIVE DEBUGGING — values + order + state, joined to source lines; trace off = clean run;"
echo "replay is free: the walker is deterministic, the trace IS the recording"

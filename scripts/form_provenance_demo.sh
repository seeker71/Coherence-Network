#!/usr/bin/env bash
# form_provenance_demo.sh — CELL PROVENANCE, the full chain live: a running
# binary's per-node framebuffer (hits) -> table row -> the ORIGINAL SOURCE
# file:line:col that created the cell -> the source line itself. The locator
# (form-provenance.fk) needs only the source text: constructors scanned in
# pre-order, converted to post-order = flatten's exact row order.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fprov.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# the ORIGINAL SOURCE — the fib program authored at a known place in this file
cat > "$work/fib-source.fk" <<'EOF'
; fib-source.fk — the original source of the fib walker program
; (cell provenance demo: every cell of the running binary points back here)
(let fibc
  (fk-if (fk-le (fk-arg) (fk-lit 1))
         (fk-arg)
         (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1)))
                 (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
EOF

# emit the SPY walker from that source + run it for the live framebuffer
cat "$FORM/form-stdlib/minimal-surface.fk" "$FORM/form-stdlib/hati-os-kernel.fk" \
    "$FORM/form-stdlib/hati-os-kernel-emit.fk" "$work/fib-source.fk" > "$work/e.fk"
printf '(print "==C==")\n(print (fkc-emit-spy (list fibc)))\n(print "==END==")\n' >> "$work/e.fk"
(cd "$FORM" && "$GO" "$work/e.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/spy.c"
"$CLANG" -O2 -o "$work/spy" "$work/spy.c"
out=(); while IFS= read -r l; do out+=("$l"); done < <("$work/spy" 10)
echo "running binary: fib(10) = ${out[0]}  (source: fib-source.fk)"
hits=""; n=$(( ${#out[@]} - 1 ))
for i in $(seq 1 $n); do hits="$hits${out[$i]} "; done

# the locator: source text -> per-row line:col (driven through the Go kernel)
src_escaped="$(python3 -c 'import sys,json; print(json.dumps(open(sys.argv[1]).read()))' "$work/fib-source.fk")"
{ cat "$FORM/form-stdlib/form-provenance.fk"; cat <<DRV
(do
    (let src $src_escaped)
    (let locs (fp-locate src))
    (defn em (i)
        (print (str_concat (int_to_str (fp-line src (nth locs i)))
               (str_concat ":" (int_to_str (fp-col src (nth locs i)))))))
    (defn ems (i) (if (eq i (len locs)) 0 (ems2 (em i) (add i 1))))
    (defn ems2 (a i) (ems i))
    (print "LOCS")
    (ems 0)
    0)
DRV
} > "$work/loc.fk"
locs=(); first=0
while IFS= read -r l; do
    [[ "$l" == "LOCS" ]] && first=1 && continue
    [[ "$first" == 1 && "$l" != "0" ]] && locs+=("$l")
done < <(cd "$FORM" && "$GO" "$work/loc.fk" 2>/dev/null)

echo
echo "CELL PROVENANCE — live hits -> table row -> ORIGINAL SOURCE line:col -> the line:"
i=0
for h in $hits; do
    lc="${locs[$i]:-?}"; line="${lc%%:*}"
    srcline="$(sed -n "${line}p" "$work/fib-source.fk" | sed 's/^[[:space:]]*//')"
    printf "  row %-2s hits %-4s <- fib-source.fk:%-5s %s\n" "$i" "$h" "$lc" "$srcline"
    i=$((i+1))
done
echo
echo "every cell of the RUNNING binary answers: which source line created me —"
echo "no kernel surgery, no side table; the source text and the table align structurally"

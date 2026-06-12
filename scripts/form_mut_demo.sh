#!/usr/bin/env bash
# form_mut_demo.sh — the MUTATION channel live: track cell creation (heap CONS)
# and pointer updates (STORE); reads stay silent. The program builds a 3-cell
# list on the HEAP, repoints one state slot, then WALKS the list (len = pure
# reads). The log shows exactly 4 events — the state genesis, nothing else —
# while the full value-trace of the same run would log every node completion.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fmut.XXXXXX")"; trap 'rm -rf "$work"' EXIT

cat "$FORM/form-stdlib/minimal-surface.fk" "$FORM/form-stdlib/fourth-walker.fk" \
    "$FORM/form-stdlib/fourth-walker-emit.fk" > "$work/e.fk"
cat >> "$work/e.fk" <<'EOF'
(let prog (fk-add (fk-store (fk-lit 0) (fk-lit 42))
                  (fk-len (fk-cons (fk-lit 3) (fk-cons (fk-lit 2)
                          (fk-cons (fk-lit 1) (fk-lit 0)))))))
(print "==MUT==")
(print (fkc-emit-mut (list prog)))
(print "==DBG==")
(print (fkc-emit-debug (list prog)))
(print "==END==")
EOF
(cd "$FORM" && "$GO" "$work/e.fk" 2>/dev/null) > "$work/e.out"
sed -n '/^==MUT==$/,/^==DBG==$/p' "$work/e.out" | sed -e '1d' -e '$d' > "$work/mut.c"
sed -n '/^==DBG==$/,/^==END==$/p' "$work/e.out" | sed -e '1d' -e '$d' > "$work/dbg.c"
"$CLANG" -O2 -o "$work/mut" "$work/mut.c"
"$CLANG" -O2 -o "$work/dbg" "$work/dbg.c"

echo "program: store mem[0] <- 42, build (cons 3 (cons 2 (cons 1 nil))) on the HEAP, then len (reads)"
echo
echo "=== the MUTATION channel (creation + pointer updates only) ==="
"$work/mut" 0 1 | sed 's/^C /C  cell /; s/^S /S  slot repointed, value /'
mutev="$("$work/mut" 0 1 | grep -c '^[CS] ')"
dbgev="$("$work/dbg" 0 9999 | grep -c '^E ')"
echo
echo "mutation events: $mutev  (3 cells born + 1 repoint — the whole state genesis)"
echo "value-trace events for the SAME run: $dbgev  (every node completion)"
echo "the reads — len walking the list, head/tail — left ZERO events: reads are derivable,"
echo "the walker is deterministic; the mutation log IS the program's state history"
echo
echo "clean-run check: $("$work/mut" 0 | wc -l | tr -d ' ') line(s) with the channel off (the value only)"
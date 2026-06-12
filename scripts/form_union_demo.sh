#!/usr/bin/env bash
# form_union_demo.sh — the m4e3/m4e4 union, witnessed: ONE self-contained binary
# that is a BMF COMPILER (mode N: digits are source tokens -> a complete new
# walker binary's C on stdout) and a FULL-SOURCE QUINE (mode 0: its own entire C,
# byte-exact). The gap in fourth-kernel.form's measured-floors block, removed.
#
# The fixpoint: literal VALUES never change row COUNTS (fkc-flat has no dedup),
# so pass 1 builds with zeros to measure, pass 2 bakes the real numbers — m4d's
# "one rebuild lands it" at full-source scale. Gates: (1) quine byte-exact vs own
# source, (2) the GRANDCHILD closes (child compiles, its quine is byte-exact too),
# (3) compile mode reproduces M2 (tokens [1,1,2], input 5 -> 22), (4) sizes.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/funion.XXXXXX")"; trap 'rm -rf "$work"' EXIT
PRELUDE() { cat "$FORM/form-stdlib/minimal-surface.fk" "$FORM/form-stdlib/fourth-walker.fk" \
                "$FORM/form-stdlib/fourth-walker-emit.fk" "$FORM/form-stdlib/fourth-union.fk"; }

# ── pass 0: extract the constant text segments + pass-1 row counts ──
{ PRELUDE; cat <<'EOF'
(let p0 (list 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0))
(let r0 (list 0 0 0 0 0 0 0 0 0 0 0))
(let f0 (fkc-flatten-many (fku-program p0 r0)))
(print "==A==")
(print (str_concat (fkc-pr-text) (str_concat (fkc-arena-decl-text) "static const long long fk_fn[")))
(print "==W==")
(print (fkc-walk-many-text))
(print "==MQ==")
(print (fku-main-quiet-text))
(print "==MS==")
(print (fkc-main-many-text))
(print "==N==")
(print (int_to_str (len (nth f0 0))))
(print "==R==")
(print (fkc-fn-text (nth f0 1)))
(print "==END==")
EOF
} > "$work/probe.fk"
(cd "$FORM" && "$GO" "$work/probe.fk" 2>/dev/null) > "$work/probe.out"
seg() { sed -n "/^==$1==\$/,/^==$2==\$/p" "$work/probe.out" | sed -e '1d' -e '$d'; }
printf '%s' "$(seg A W)"   > "$work/segA.txt"
printf '%s' "$(seg W MQ)"  > "$work/segW.txt"
printf '%s' "$(seg MQ MS)" > "$work/segMQ.txt"
printf '%s' "$(seg MS N)"  > "$work/segMS.txt"
printf '%s' '] = { '                                  > "$work/segS1.txt"
printf '%s' ' }; static const long long fk_node['    > "$work/segS2.txt"
printf '%s' '][4] = { '                               > "$work/segS3.txt"
printf '%s' ' }; '                                    > "$work/segS4.txt"
FNROWS="$(seg N R)"; ROOTS="$(seg R END)"
echo "pass 1: $FNROWS function rows; roots: $ROOTS"

# ── pack each segment into 4-chars-per-row data rows; compute the bounds ──
pack() { od -An -v -tu1 "$1" | tr -s ' ' '\n' | grep -v '^$' | \
         awk '{b[(NR-1)%4]=$1; if (NR%4==0) {print "(list "b[0]" "b[1]" "b[2]" "b[3]")"; d=1}} END {if (NR%4!=0) {for(i=NR%4;i<4;i++)b[i]=0; print "(list "b[0]" "b[1]" "b[2]" "b[3]")"}}'; }
idx=$FNROWS; bounds=""
for s in A S1 S2 S3 S4 W MQ MS; do
    pack "$work/seg$s.txt" > "$work/rows$s.fk"
    n=$(wc -l < "$work/rows$s.fk" | tr -d ' ')
    bounds="$bounds $idx $((idx + n - 1))"
    idx=$((idx + n))
done
GS=$idx
printf '(list 1 3 10 0)\n(list 2 4 3 0)\n' > "$work/rowsG.fk"   # the M2 grammar as data rows
NR=$((idx + 2)); NF=11
read -r AS AE S1S S1E S2S S2E S3S S3E S4S S4E WS WE MQS MQE MSS MSE <<< "$bounds"
echo "pass 2: NR=$NR; segments A[$AS..$AE] W[$WS..$WE] MQ[$MQS..$MQE] MS[$MSS..$MSE] G[$GS]"

# ── pass 2: bake the real literals, attach the data rows, emit the union C ──
{ PRELUDE
  echo "(let p (list $NF $NR $AS $AE $S1S $S1E $S2S $S2E $S3S $S3E $S4S $S4E $WS $WE $MQS $MQE $MSS $MSE $GS))"
  echo "(let roots (list $(echo "$ROOTS" | tr ',' ' ')))"
  echo "(let data (list"
  cat "$work"/rows{A,S1,S2,S3,S4,W,MQ,MS,G}.fk
  echo "))"
  cat <<'EOF'
(let flat (fku-with-data (fkc-flatten-many (fku-program p roots)) data))
(print "==C==")
(print (fku-emit-c (nth flat 0) (nth flat 1)))
(print "==END==")
EOF
} > "$work/build.fk"
(cd "$FORM" && "$GO" "$work/build.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/union.c"
[[ -s "$work/union.c" ]] || { echo "FAIL: no C emitted"; exit 1; }
"$CLANG" -O2 -o "$work/union" "$work/union.c" || { echo "FAIL: clang"; exit 1; }
echo "union binary: $(wc -c < "$work/union" | tr -d ' ') bytes  (C source: $(wc -c < "$work/union.c" | tr -d ' ') bytes)"

# ── gate 1: the FULL-SOURCE quine — mode 0 output == its own source, byte-exact ──
"$work/union" 0 > "$work/self.c"
if cmp -s "$work/self.c" "$work/union.c"; then
    echo "GATE 1  quine: mode 0 emitted its OWN ENTIRE C source, byte-exact"
else
    echo "GATE 1 FAIL: self-emission differs ($(cmp "$work/self.c" "$work/union.c" 2>&1 | head -1))"; exit 1
fi

# ── gate 2: the grandchild — compile the self-emission, ITS quine must close too ──
"$CLANG" -O2 -o "$work/union2" "$work/self.c"
"$work/union2" 0 > "$work/self2.c"
if cmp -s "$work/self2.c" "$work/union.c"; then
    echo "GATE 2  grandchild: the reproduced binary reproduces, byte-exact — the loop closes"
else
    echo "GATE 2 FAIL"; exit 1
fi

# ── gate 3: the BMF compiler — tokens [1,1,2] through the baked grammar = M2 ──
"$work/union" 112 > "$work/prog.c"
"$CLANG" -O2 -o "$work/prog" "$work/prog.c" || { echo "GATE 3 FAIL: emitted C does not compile"; exit 1; }
v="$("$work/prog" 5 | head -1)"
if [[ "$v" == "22" ]]; then
    echo "GATE 3  compiler: mode 112 -> a complete new binary; (5+10+10)-3 = $v (the M2 check)"
else
    echo "GATE 3 FAIL: expected 22, got $v"; exit 1
fi

echo
echo "THE GAP IS REMOVED — one self-contained binary ($(wc -c < "$work/union" | tr -d ' ') bytes + 0-byte pack):"
echo "  mode 0  reproduces its entire source byte-exactly (and the grandchild closes)"
echo "  mode N  is a BMF compiler: digit-tokens through the grammar -> a new walker binary"
echo "  the same printer serves both — the quine's emitter IS the compiler's emitter"

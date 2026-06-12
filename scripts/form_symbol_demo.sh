#!/usr/bin/env bash
# form_symbol_demo.sh — SOURCE-SYMBOL LOOKUP FROM FRAMEBUFFER INSPECTION. The spy
# walker counts fk_hits per TABLE ROW (the per-node framebuffer); row i IS source
# node i; so inspecting a RUNNING binary yields, per node: hits | the symbol the
# node renders to (asm pack | English pack). Reasoning about the binary becomes
# reading its own source vocabulary weighted by its own live execution.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fsym.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# emit the SPY fib walker (per-node framebuffer) and its table rows
cat "$FORM/form-stdlib/minimal-surface.fk" "$FORM/form-stdlib/hati-os-kernel.fk" \
    "$FORM/form-stdlib/hati-os-kernel-emit.fk" > "$work/e.fk"
cat >> "$work/e.fk" <<'EOF'
(let fibc (fk-if (fk-le (fk-arg) (fk-lit 1)) (fk-arg) (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1))) (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
(let flat (fkc-flatten-many (list fibc)))
(print "==C==")
(print (fkc-emit-spy (list fibc)))
(print "==ROWS==")
(print (fkc-rows-text (nth flat 0)))
(print "==END==")
EOF
(cd "$FORM" && "$GO" "$work/e.fk" 2>/dev/null) > "$work/e.out"
sed -n '/^==C==$/,/^==ROWS==$/p' "$work/e.out" | sed -e '1d' -e '$d' > "$work/spy.c"
ROWS="$(sed -n '/^==ROWS==$/,/^==END==$/p' "$work/e.out" | sed -e '1d' -e '$d')"
"$CLANG" -O2 -o "$work/spy" "$work/spy.c"

# run it: the value, then the LIVE per-node framebuffer
out=(); while IFS= read -r l; do out+=("$l"); done < <("$work/spy" 10)
echo "running binary: fib(10) = ${out[0]} — per-NODE framebuffer captured live"
hits=""; n=$(( ${#out[@]} - 1 ))
for i in $(seq 1 $n); do hits="$hits${out[$i]} "; done

# the inspector: join hits -> node -> symbol, rendered at two levels
cat "$FORM/form-stdlib/form-diagnose.fk" > "$work/i.fk"
python3 - "$work/i.fk" "$ROWS" "$hits" <<'PY'
import sys
path, rows_text, hits = sys.argv[1], sys.argv[2], sys.argv[3]
rows = [r for r in rows_text.replace('},','}|').split('|') if r.strip()]
rows_fk = " ".join("(list " + r.strip()[1:-1].replace(',', ' ') + ")" for r in rows)
hits_fk = "(list " + hits.strip() + ")"
drv = f"""
    (let prog (list {rows_fk}))
    (let hits {hits_fk})
    (defn ptag (i) (nth (nth prog i) 0))
    (defn pc1  (i) (nth (nth prog i) 1))
    (defn pc2  (i) (nth (nth prog i) 2))
    (defn pc3  (i) (nth (nth prog i) 3))
    (defn rasm (i)
        (if (eq (ptag i) 1) (int_to_str (pc1 i))
        (if (eq (ptag i) 2) "ARG"
        (if (eq (ptag i) 3) (str_concat "(ADD " (str_concat (rasm (pc1 i)) (str_concat " " (str_concat (rasm (pc2 i)) ")"))))
        (if (eq (ptag i) 4) (str_concat "(SUB " (str_concat (rasm (pc1 i)) (str_concat " " (str_concat (rasm (pc2 i)) ")"))))
        (if (eq (ptag i) 5) (str_concat "(LE " (str_concat (rasm (pc1 i)) (str_concat " " (str_concat (rasm (pc2 i)) ")"))))
        (if (eq (ptag i) 6) (str_concat "(IF " (str_concat (rasm (pc1 i)) " ...)"))
        (if (eq (ptag i) 12) (str_concat "(CALL fib " (str_concat (rasm (pc2 i)) ")"))
            "?")))))))) 
    (defn reng (i)
        (if (eq (ptag i) 1) (int_to_str (pc1 i))
        (if (eq (ptag i) 2) "the input n"
        (if (eq (ptag i) 3) (str_concat (reng (pc1 i)) (str_concat " plus " (reng (pc2 i))))
        (if (eq (ptag i) 4) (str_concat (reng (pc1 i)) (str_concat " minus " (reng (pc2 i))))
        (if (eq (ptag i) 5) (str_concat (reng (pc1 i)) (str_concat " is at most " (reng (pc2 i))))
        (if (eq (ptag i) 6) (str_concat "if " (str_concat (reng (pc1 i)) ", choose"))
        (if (eq (ptag i) 12) (str_concat "fib of " (reng (pc2 i)))
            "?")))))))) 
    (defn row (i)
        (print (str_concat "node " (str_concat (int_to_str i)
               (str_concat "  hits " (str_concat (int_to_str (fd-vat hits i))
               (str_concat "\t" (str_concat (rasm i)
               (str_concat "   |   " (reng i))))))))))
    (defn rows2 (i) (if (eq i (len hits)) 0 (rows3 (row i) (add i 1))))
    (defn rows3 (a i) (rows2 i))
    (print "TABLE")
    (rows2 0)
    (print (str_concat "HOT " (int_to_str (fd-vhot hits))))
    (print (str_concat "NDEAD " (int_to_str (len (fd-vdead hits)))))
    0)
"""
s = open(path).read()
# close the two preludes' (do ...) blocks are separate files each ending '0)'?? — both
# core.fk and form-diagnose.fk are full files; append driver as its own (do ...)
s = s + "\n(do\n" + drv + "\n"
open(path,'w').write(s)
PY
echo
echo "SOURCE-SYMBOL LOOKUP from the live framebuffer (node | hits | asm | English):"
out2="$(cd "$FORM" && "$GO" "$work/i.fk" 2>/dev/null)"
echo "$out2" | sed -n '/^TABLE$/,$p' | sed '1d' | grep -v '^0$' | grep -v '^HOT\|^NDEAD'
hot="$(echo "$out2" | grep '^HOT' | awk '{print $2}')"
ndead="$(echo "$out2" | grep '^NDEAD' | awk '{print $2}')"
echo
echo "the organ's reading: hottest source node = $hot; never-executed nodes = $ndead"
echo "REASONING ABOUT THE BINARY = reading its own source symbols weighted by its live breath"

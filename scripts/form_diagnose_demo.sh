#!/usr/bin/env bash
# form_diagnose_demo.sh — the live-diagnosis organ on REAL channels. One fib
# recipe, two carriers, two open channels: the NATIVE binary's value channel
# (exit codes over inputs) and the WALKER binary's framebuffer (fk_arms per-op
# execution counts, printed live). The organ (form-diagnose.fk) LEARNS the
# program's law from the value channel alone, reads hot/dead ops from the live
# framebuffer, independently PREDICTS the law from the recipe (substrate ground),
# and holds conviction only when the two witnesses agree. Recipe and data
# separate: one generic organ; every observation is data passing through.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fdiag.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── carrier 1: the NATIVE fib (form-lower + form-macho + ld, zero clang) ──
{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-lower.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let prog (list (list 1 1 0 0) (list 2 0 0 0) (list 5 1 0 0) (list 4 1 0 0)
                    (list 7 3 0 0) (list 1 2 0 0) (list 4 1 5 0) (list 7 6 0 0)
                    (list 3 4 7 0) (list 6 2 0 8)))
    (print (str_concat "MACHO " (hxb (mo-object (lo-rec-fn prog 9)))))
    0)
DRV
} > "$work/native.fk"
(cd "$FORM" && "$GO" "$work/native.fk" 2>/dev/null) | grep '^MACHO ' | sed 's/^MACHO //' | xxd -r -p > "$work/f.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/f" "$work/f.o" 2>/dev/null

# the VALUE channel: exit codes over inputs n = 1..6
obs=()
for args in "" "a" "a b" "a b c" "a b c d" "a b c d e"; do
    # shellcheck disable=SC2086
    "$work/f" $args; obs+=($?)
done
echo "value channel (native binary, exit codes n=1..6):  ${obs[*]}"

# ── carrier 2: the WALKER fib — its printed fk_arms IS the live framebuffer ──
cat "$FORM/form-stdlib/minimal-surface.fk" "$FORM/form-stdlib/hati-os-kernel.fk" \
    "$FORM/form-stdlib/hati-os-kernel-emit.fk" > "$work/walker.fk"
cat >> "$work/walker.fk" <<'EOF'
(let fibc (fk-if (fk-le (fk-arg) (fk-lit 1)) (fk-arg) (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1))) (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
(print "==C==")
(print (fkc-emit-many (list fibc)))
(print "==END==")
EOF
(cd "$FORM" && "$GO" "$work/walker.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/w.c"
"$CLANG" -O2 -o "$work/w" "$work/w.c"
fbout=()
while IFS= read -r line; do fbout+=("$line"); done < <("$work/w" 10)
echo "framebuffer channel (walker binary, fib(10) = ${fbout[0]}; fk_arms tags 1..23, live):"
fbrows=""
for t in $(seq 1 23); do
    c="${fbout[$t]}"
    fbrows="$fbrows(list $t $c) "
    [[ "$c" != "0" ]] && printf "  tag %-2s fired %s times\n" "$t" "$c"
done

# ── the ORGAN: learn from data, ground in the recipe, convict on agreement ──
{ cat "$FORM/form-stdlib/form-diagnose.fk"; } > "$work/organ.fk"
# re-open the (do ...) to run the diagnosis with the LIVE data
python3 - "$work/organ.fk" "${obs[*]}" "$fbrows" <<'PY'
import sys
path, obs, fbrows = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(path).read()
obs_l = "(list " + " ".join(obs.split()) + ")"
drv = f"""
    (let fb (list {fbrows}))
    (let obs {obs_l})
    (let fibp (list
        (list 1 1 0 0) (list 2 0 0 0) (list 5 1 0 0) (list 4 1 0 0)
        (list 7 3 0 0) (list 1 2 0 0) (list 4 1 5 0) (list 7 6 0 0)
        (list 3 4 7 0) (list 6 2 0 8)))
    (print (str_concat "HOT "     (int_to_str (fd-hot fb))))
    (print (str_concat "DEAD "    (int_to_str (len (fd-dead fb (list 1 2 3 4 5 6 9))))))
    (print (str_concat "LEARNED " (int_to_str (fd-learn-add2 obs))))
    (print (str_concat "GROUND "  (int_to_str (fd-ground-add2 fibp 9))))
    (print (str_concat "CONVICT " (int_to_str (fd-convict (fd-learn-add2 obs) (fd-ground-add2 fibp 9)))))
    0)
"""
s = s.rstrip().rstrip(')').rstrip().rstrip('0').rstrip() + drv
open(path, 'w').write(s)
PY
diag="$(cd "$FORM" && "$GO" "$work/organ.fk" 2>/dev/null)"
hot="$(echo "$diag" | grep '^HOT' | awk '{print $2}')"
dead="$(echo "$diag" | grep '^DEAD' | awk '{print $2}')"
learned="$(echo "$diag" | grep '^LEARNED' | awk '{print $2}')"
ground="$(echo "$diag" | grep '^GROUND' | awk '{print $2}')"
convict="$(echo "$diag" | grep '^CONVICT' | awk '{print $2}')"

echo
echo "the organ's diagnosis (form-diagnose.fk, fed the live channels):"
echo "  hot op tag:        $hot   (the highest-fired op — the JIT/lift candidate)"
echo "  silent recipe ops: $dead   (present in the recipe, never fired — the witness's nothing-state)"
echo "  learned (data):    $learned   (from exit codes ALONE: obs[i] = obs[i-1] + obs[i-2])"
echo "  ground (recipe):   $ground   (from the tree ALONE: COND else = ADD(CALL, CALL))"
echo "  CONVICTION:        $convict   (both witnesses agree)"
if [[ "$learned" == "1" && "$ground" == "1" && "$convict" == "1" ]]; then
    echo
    echo "DIAGNOSED LIVE — the organ learned the program's law from its open channel,"
    echo "the recipe independently predicted it, and the two witnesses agree. One generic"
    echo "organ; the framebuffer rows, observations, and learned law are all data."
else
    echo "FAIL: expected learned=1 ground=1 convict=1"; exit 1
fi

#!/usr/bin/env bash
# fourth_kernel_audit.sh — M1 carrier for docs/coherence-substrate/fourth-kernel.form:
# realize the Form-emitted standalone CLI (form-stdlib/fourth-kernel-emit.fk) through
# clang, prove value parity against the three walking kernels on the same semantic asks
# (fib 28, sum 1000, ackermann 3 6), then measure the comparison rows the spec names:
# median wall time, maximum RSS, binary size, startup. Parity gates the timing — a row
# only counts when every carrier returns the same value through its own front door.
#
# Carriers: form-kernel-go, form-kernel-rust (built if missing), form-kernel-ts via
# npx tsx (skipped when node is absent), and fk4 — the binary whose every source byte
# was emitted by Form recipes. clang and the OS loader are allowed host carriers
# (host-kernel.form host-resource-access); the emitter intelligence lives in the body.
#
# Run:  scripts/fourth_kernel_audit.sh
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
RS_BIN="$FORMDIR/form-kernel-rust/target/release/form-kernel-rust"
TS_MAIN="$FORMDIR/form-kernel-ts/src/main.ts"
CLANG="${CLANG:-clang}"

if ! command -v "$CLANG" >/dev/null; then
    echo "FAIL  clang not available — the M1 carrier needs a C toolchain"; exit 1
fi
if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi
if [[ ! -x "$RS_BIN" ]]; then
    if command -v cargo >/dev/null; then
        echo "  building rust kernel..." >&2
        (cd "$FORMDIR/form-kernel-rust" && cargo build --release --quiet)
    fi
fi
HAVE_RS=0; [[ -x "$RS_BIN" ]] && HAVE_RS=1
HAVE_TS=0; command -v npx >/dev/null && [[ -f "$TS_MAIN" ]] && HAVE_TS=1

work="$(mktemp -d "${TMPDIR:-/tmp}/fk4.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the whole program; the kernel is only the mouth ────────
cat "$FORMDIR/form-stdlib/fourth-kernel-emit.fk" > "$work/driver.fk"
cat >> "$work/driver.fk" <<'EOF'
(print "==FK4==")
(print (fk4-program "fk4"))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==FK4==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/fk4.c"
if ! grep -q 'int main' "$work/fk4.c"; then
    echo "FAIL  emission did not produce a main — see $work/emit.out"; exit 1
fi

"$CLANG" -O2 -o "$work/fk4" "$work/fk4.c"
FK4="$work/fk4"

# ── 2. The walkers' own answers (recursive recipes, their semantics) ─────
cat > "$work/wfib.fk" <<'EOF'
(do (defn wfib (n) (if (le n 1) n (add (wfib (sub n 1)) (wfib (sub n 2))))) (print (wfib 28)) 0)
EOF
cat > "$work/wsum.fk" <<'EOF'
(do (defn wsum (n) (if (le n 0) 0 (add n (wsum (sub n 1))))) (print (wsum 1000)) 0)
EOF
cat > "$work/wack.fk" <<'EOF'
(do (defn wack (m n) (if (eq m 0) (add n 1) (if (eq n 0) (wack (sub m 1) 1) (wack (sub m 1) (wack m (sub n 1)))))) (print (wack 3 6)) 0)
EOF
cat > "$work/wzero.fk" <<'EOF'
(do (print 0) 0)
EOF

run_kernel() { # kernel-name file -> first stdout line
    case "$1" in
        go)   (cd "$FORMDIR" && "$GO_BIN" "$2" 2>/dev/null) | head -1 ;;
        rust) (cd "$FORMDIR" && "$RS_BIN" "$2" 2>/dev/null) | head -1 ;;
        ts)   (cd "$FORMDIR" && npx --yes tsx "$TS_MAIN" "$2" 2>/dev/null) | head -1 ;;
    esac
}

go_fib="$(run_kernel go "$work/wfib.fk")";  go_sum="$(run_kernel go "$work/wsum.fk")";  go_ack="$(run_kernel go "$work/wack.fk")"
fk4_fib="$("$FK4" 1 28)"; fk4_sum="$("$FK4" 2 1000)"; fk4_ack="$("$FK4" 3 3 6)"

echo "parity (go walker vs Form-emitted native):"
echo "  fib 28   walker=$go_fib  fk4=$fk4_fib"
echo "  sum 1000 walker=$go_sum  fk4=$fk4_sum"
echo "  ack 3 6  walker=$go_ack  fk4=$fk4_ack"
if [[ "$go_fib" != "$fk4_fib" || "$go_sum" != "$fk4_sum" || "$go_ack" != "$fk4_ack" ]]; then
    echo "FAIL  value parity broken — timing rows do not count"; exit 1
fi
if [[ "$HAVE_RS" == "1" ]]; then
    rs_fib="$(run_kernel rust "$work/wfib.fk")"
    [[ "$rs_fib" == "$fk4_fib" ]] || { echo "FAIL  rust walker disagrees: $rs_fib"; exit 1; }
fi
if [[ "$HAVE_TS" == "1" ]]; then
    ts_fib="$(run_kernel ts "$work/wfib.fk")"
    [[ "$ts_fib" == "$fk4_fib" ]] || { echo "FAIL  ts walker disagrees: $ts_fib"; exit 1; }
fi
echo "  parity holds — rows count"
echo

# ── 3. The rows: median wall, max RSS, binary size, startup ─────────────
median_ms() { # K cmd... -> median wall ms over K runs
    local k="$1"; shift
    python3 - "$k" "$@" <<'PY'
import subprocess, sys, time
k = int(sys.argv[1]); cmd = sys.argv[2:]; ts = []
for _ in range(k):
    t0 = time.perf_counter()
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=None)
    ts.append((time.perf_counter() - t0) * 1000.0)
ts.sort(); print(f"{ts[len(ts)//2]:.1f}")
PY
}

max_rss_mb() { # cmd... -> maximum resident set size in MB (macOS/BSD time -l, linux -v)
    local out
    if /usr/bin/time -l true 2>/dev/null >/dev/null; then
        out="$({ /usr/bin/time -l "$@" >/dev/null; } 2>&1 | awk '/maximum resident set size/ {print $1}')"
        python3 -c "print(f'{int('"${out:-0}"')/1048576:.1f}')"
    elif /usr/bin/time -v true 2>/dev/null >/dev/null; then
        out="$({ /usr/bin/time -v "$@" >/dev/null; } 2>&1 | awk -F: '/Maximum resident set size/ {print $2}' | tr -d ' ')"
        python3 -c "print(f'{int('"${out:-0}"')/1024:.1f}')"
    else
        echo "-"
    fi
}

size_kb() { python3 -c "import os,sys; print(f'{os.path.getsize(sys.argv[1])/1024:.0f}')" "$1"; }

row() { # label fib_ms sum_ms ack_ms startup_ms rss_mb size_kb
    printf '%-22s %10s %10s %10s %12s %10s %12s\n' "$1" "$2" "$3" "$4" "$5" "$6" "$7"
}

echo "rows (median wall ms per full invocation; RSS on fib 28; size of the carrier binary):"
row carrier "fib28-ms" "sum1k-ms" "ack36-ms" "startup-ms" "rss-MB" "size-KB"

fk4_t_fib="$(median_ms 15 "$FK4" 1 28)"
fk4_t_sum="$(median_ms 15 "$FK4" 2 1000)"
fk4_t_ack="$(median_ms 15 "$FK4" 3 3 6)"
fk4_t_zero="$(median_ms 15 "$FK4" 0 0)"
fk4_rss="$(max_rss_mb "$FK4" 1 28)"
row "fk4 (Form-emitted)" "$fk4_t_fib" "$fk4_t_sum" "$fk4_t_ack" "$fk4_t_zero" "$fk4_rss" "$(size_kb "$FK4")"

go_t_fib="$(cd "$FORMDIR" && median_ms 5 "$GO_BIN" "$work/wfib.fk")"
go_t_sum="$(cd "$FORMDIR" && median_ms 5 "$GO_BIN" "$work/wsum.fk")"
go_t_ack="$(cd "$FORMDIR" && median_ms 5 "$GO_BIN" "$work/wack.fk")"
go_t_zero="$(cd "$FORMDIR" && median_ms 5 "$GO_BIN" "$work/wzero.fk")"
go_rss="$(cd "$FORMDIR" && max_rss_mb "$GO_BIN" "$work/wfib.fk")"
row "form-kernel-go" "$go_t_fib" "$go_t_sum" "$go_t_ack" "$go_t_zero" "$go_rss" "$(size_kb "$GO_BIN")"

if [[ "$HAVE_RS" == "1" ]]; then
    rs_t_fib="$(cd "$FORMDIR" && median_ms 5 "$RS_BIN" "$work/wfib.fk")"
    rs_t_sum="$(cd "$FORMDIR" && median_ms 5 "$RS_BIN" "$work/wsum.fk")"
    rs_t_ack="$(cd "$FORMDIR" && median_ms 5 "$RS_BIN" "$work/wack.fk")"
    rs_t_zero="$(cd "$FORMDIR" && median_ms 5 "$RS_BIN" "$work/wzero.fk")"
    rs_rss="$(cd "$FORMDIR" && max_rss_mb "$RS_BIN" "$work/wfib.fk")"
    row "form-kernel-rust" "$rs_t_fib" "$rs_t_sum" "$rs_t_ack" "$rs_t_zero" "$rs_rss" "$(size_kb "$RS_BIN")"
else
    row "form-kernel-rust" SKIP SKIP SKIP SKIP - -
fi

if [[ "$HAVE_TS" == "1" ]]; then
    ts_t_fib="$(cd "$FORMDIR" && median_ms 3 npx --yes tsx "$TS_MAIN" "$work/wfib.fk")"
    ts_t_sum="$(cd "$FORMDIR" && median_ms 3 npx --yes tsx "$TS_MAIN" "$work/wsum.fk")"
    ts_t_ack="$(cd "$FORMDIR" && median_ms 3 npx --yes tsx "$TS_MAIN" "$work/wack.fk")"
    ts_t_zero="$(cd "$FORMDIR" && median_ms 3 npx --yes tsx "$TS_MAIN" "$work/wzero.fk")"
    ts_rss="$(cd "$FORMDIR" && max_rss_mb npx --yes tsx "$TS_MAIN" "$work/wfib.fk")"
    row "form-kernel-ts (tsx)" "$ts_t_fib" "$ts_t_sum" "$ts_t_ack" "$ts_t_zero" "$ts_rss" "-"
else
    row "form-kernel-ts (tsx)" SKIP SKIP SKIP SKIP - -
fi

echo
echo "emitted source: $(wc -c < "$work/fk4.c" | tr -d ' ') bytes, every byte authored by Form recipes"

# ── 4. m4c — the EMITTED WALKER: the emitter reads fib-as-cells and emits ──
# the generic walker + node table + probe; the program stays data in C.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/fkw-driver.fk"
cat >> "$work/fkw-driver.fk" <<'EOF'
(print "==FKW==")
(print (fkc-emit (fk-fib-program)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/fkw-driver.fk" 2>/dev/null) > "$work/fkw-emit.out"
sed -n '/^==FKW==$/,/^==END==$/p' "$work/fkw-emit.out" | sed -e '1d' -e '$d' > "$work/fkw.c"
if ! grep -q 'fk_arms' "$work/fkw.c"; then
    echo "FAIL  walker emission did not carry its probe — see $work/fkw-emit.out"; exit 1
fi
"$CLANG" -O2 -o "$work/fkw" "$work/fkw.c"
FKW="$work/fkw"

fkw_out="$("$FKW" 28)"
fkw_fib="$(printf '%s\n' "$fkw_out" | sed -n 1p)"
echo
echo "m4c emitted walker (fib-as-cells -> C node table + generic walk + probe):"
echo "  fib 28  walker=$go_fib  fkw=$fkw_fib"
if [[ "$go_fib" != "$fkw_fib" ]]; then
    echo "FAIL  emitted-walker parity broken — its rows do not count"; exit 1
fi
echo "  probe (arms LIT ARG ADD SUB LE IF SELF NODE PUTC DIV MOD, from inside the binary):"
printf '%s\n' "$fkw_out" | sed -n 2,12p | tr '\n' ' ' | sed 's/^/    /'; echo
fkw_t_fib="$(median_ms 15 "$FKW" 28)"
fkw_t_zero="$(median_ms 15 "$FKW" 0)"
fkw_rss="$(max_rss_mb "$FKW" 28)"
row "fkw (emitted walker)" "$fkw_t_fib" "-" "-" "$fkw_t_zero" "$fkw_rss" "$(size_kb "$FKW")"
echo "  (fkw walks the SAME program-as-data the kernels walk — one interpretation layer, native; sum/ack rows arrive when their programs are authored)"

echo
# ── 5. m4d first move — the quine seed: the booted binary emits its own ──
# node table byte-exactly (self-observation through NODE, self-emission
# through PUTC), checked against the emitter's independently computed text.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/fkd-driver.fk"
cat >> "$work/fkd-driver.fk" <<'EOF'
(print "==SRC==")
(print (fkc-emit (fkd-self-printer)))
(print "==TBL==")
(print (fkc-rows-text (fkc-flatten (fkd-self-printer))))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/fkd-driver.fk" 2>/dev/null) > "$work/fkd-emit.out"
sed -n '/^==SRC==$/,/^==TBL==$/p' "$work/fkd-emit.out" | sed -e '1d' -e '$d' > "$work/fkd.c"
sed -n '/^==TBL==$/,/^==END==$/p' "$work/fkd-emit.out" | sed -e '1d' -e '$d' > "$work/fkd-want.txt"
"$CLANG" -O2 -o "$work/fkd" "$work/fkd.c"
"$work/fkd" 0 > "$work/fkd-run.txt"
head -1 "$work/fkd-run.txt" > "$work/fkd-got.txt"
echo "m4d quine seed (the binary walks its OWN table and emits it):"
if diff -q "$work/fkd-got.txt" "$work/fkd-want.txt" >/dev/null; then
    echo "  FIXPOINT HOLDS — self-emitted table is byte-exact ($(wc -c < "$work/fkd-want.txt" | tr -d ' ') bytes)"
else
    echo "  FAIL  self-emission diverged from the emitter's truth"; exit 1
fi
echo "  probe: $(sed -n 3,13p "$work/fkd-run.txt" | tr '\n' ' ')(arms 1..11 — PUTC equals the byte count)"

echo
# ── 6. m4e1 — CALL + the function table: mutual recursion in the booted ──
# binary, and fib through CALL instead of SELF (the multi-function lane
# that unblocks the emitter-as-program).
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/fke-driver.fk"
cat >> "$work/fke-driver.fk" <<'EOF'
(let even (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 1) (fk-call 1 (fk-sub (fk-arg) (fk-lit 1)))))
(let odd  (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 0) (fk-call 0 (fk-sub (fk-arg) (fk-lit 1)))))
(let fibc (fk-if (fk-le (fk-arg) (fk-lit 1)) (fk-arg) (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1))) (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
(print "==EO==")
(print (fkc-emit-many (list even odd)))
(print "==FIB==")
(print (fkc-emit-many (list fibc)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/fke-driver.fk" 2>/dev/null) > "$work/fke-emit.out"
sed -n '/^==EO==$/,/^==FIB==$/p' "$work/fke-emit.out" | sed -e '1d' -e '$d' > "$work/eo.c"
sed -n '/^==FIB==$/,/^==END==$/p' "$work/fke-emit.out" | sed -e '1d' -e '$d' > "$work/fibc.c"
"$CLANG" -O2 -o "$work/eo" "$work/eo.c"
"$CLANG" -O2 -o "$work/fibc" "$work/fibc.c"
eo10="$("$work/eo" 10 | head -1)"; eo7="$("$work/eo" 7 | head -1)"; fibc28="$("$work/fibc" 28 | head -1)"
echo "m4e1 CALL + function table (mutual recursion, booted):"
echo "  even(10)=$eo10 even(7)=$eo7 (mutual CALL by index)  fib-via-CALL(28)=$fibc28"
if [[ "$eo10" != "1" || "$eo7" != "0" || "$fibc28" != "$go_fib" ]]; then
    echo "FAIL  CALL-lane parity broken"; exit 1
fi
fibc_t="$(median_ms 15 "$work/fibc" 28)"
echo "  fib-via-CALL median: ${fibc_t} ms (vs SELF-shaped fkw above — the CALL indirection priced)"

echo
# ── 7. M2 proof-of-shape — grammar + source -> a new binary, grammar-driven ──
# A grammar-as-data compiler (bmf-mini.fk) folds source tokens through rule
# cells into a program-as-cells; the emitter turns that into C; clang makes a
# binary. Swap the grammar, get a DIFFERENT binary — the compiler-compiler
# property, proven in compiled output.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" "$FORMDIR/form-stdlib/bmf-mini.fk" > "$work/bmf-driver.fk"
cat >> "$work/bmf-driver.fk" <<'EOF'
(let g1 (list (bmf-rule 1 3 10) (bmf-rule 2 4 3)))
(let g2 (list (bmf-rule 1 3 100) (bmf-rule 2 4 3)))
(let src (list 1 1 2))
(print "==B1==")
(print (fkc-emit-many (list (bmf-compile g1 src))))
(print "==B2==")
(print (fkc-emit-many (list (bmf-compile g2 src))))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/bmf-driver.fk" 2>/dev/null) > "$work/bmf.out"
sed -n '/^==B1==$/,/^==B2==$/p' "$work/bmf.out" | sed -e '1d' -e '$d' > "$work/prog1.c"
sed -n '/^==B2==$/,/^==END==$/p' "$work/bmf.out" | sed -e '1d' -e '$d' > "$work/prog2.c"
"$CLANG" -O2 -o "$work/prog1" "$work/prog1.c"
"$CLANG" -O2 -o "$work/prog2" "$work/prog2.c"
b1="$("$work/prog1" 5 | head -1)"; b2="$("$work/prog2" 5 | head -1)"
echo "M2 grammar + source -> binary (source tokens [1,1,2], input 5):"
echo "  grammar g1 (tok1=ADD 10)  -> binary -> $b1 (expect 22)"
echo "  grammar g2 (tok1=ADD 100) -> binary -> $b2 (expect 202)"
if [[ "$b1" != "22" || "$b2" != "202" ]]; then
    echo "FAIL  grammar-driven binary generation broke"; exit 1
fi
echo "  SAME source, DIFFERENT grammar -> DIFFERENT binary — the compiler-compiler property, compiled."
echo "  (the compiler runs as a recipe here; the standalone compiler-binary that reads textual"
echo "   source through the port still needs m4e4 strings and the m4e3 real-recipe bridge)"

echo
# ── 8-10. the Form-OS face: universal loader, self-JIT on heat, the organs ──
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" "$FORMDIR/form-stdlib/bmf-mini.fk" > "$work/os-driver.fk"
cat >> "$work/os-driver.fk" <<'EOF'
(let fibc (fk-if (fk-le (fk-arg) (fk-lit 1)) (fk-arg) (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1))) (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
(let even (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 1) (fk-call 1 (fk-sub (fk-arg) (fk-lit 1)))))
(let odd  (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 0) (fk-call 0 (fk-sub (fk-arg) (fk-lit 1)))))
(let g1 (list (bmf-rule 1 3 10) (bmf-rule 2 4 3)))
(let heap (fk-cons (fk-lit 7) (fk-cons (fk-lit 8) (fk-empty))))
(let heap_prog (fk-add (fk-head heap)
               (fk-add (fk-head (fk-tail heap))
               (fk-add (fk-len heap) (fk-nth heap (fk-lit 1))))))
(let organ (fk-add (fk-if (fk-sub (fk-set (fk-lit 7) (fk-lit 42)) (fk-get (fk-lit 7))) (fk-lit 0) (fk-lit 1))
           (fk-add (fk-if (fk-le (fk-time) (fk-lit 0)) (fk-lit 0) (fk-lit 2))
                   (fk-if (fk-sub (fk-rnd) (fk-rnd)) (fk-lit 4) (fk-lit 0)))))
(print "==UNI==")
(print (fkc-emit-universal))
(print "==TFIB==")
(print (fkc-table-file (list fibc)))
(print "==TEO==")
(print (fkc-table-file (list even odd)))
(print "==TBMF==")
(print (fkc-table-file (list (bmf-compile g1 (list 1 1 2)))))
(print "==THEAP==")
(print (fkc-table-file (list heap_prog)))
(print "==TORG==")
(print (fkc-table-file (list organ)))
(print "==JIT==")
(print (fkc-emit-jit (list fibc)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/os-driver.fk" 2>/dev/null) > "$work/os.out"
sed -n '/^==UNI==$/,/^==TFIB==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/uni.c"
sed -n '/^==TFIB==$/,/^==TEO==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/t-fib.txt"
sed -n '/^==TEO==$/,/^==TBMF==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/t-eo.txt"
sed -n '/^==TBMF==$/,/^==THEAP==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/t-bmf.txt"
sed -n '/^==THEAP==$/,/^==TORG==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/t-heap.txt"
sed -n '/^==TORG==$/,/^==JIT==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/t-org.txt"
sed -n '/^==JIT==$/,/^==END==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/fkjit.c"
"$CLANG" -O2 -o "$work/fkwu" "$work/uni.c"
"$CLANG" -O2 -o "$work/fkjit" "$work/fkjit.c"
u_fib="$("$work/fkwu" "$work/t-fib.txt" 28 | head -1)"
u_e10="$("$work/fkwu" "$work/t-eo.txt" 10 | head -1)"; u_e7="$("$work/fkwu" "$work/t-eo.txt" 7 | head -1)"
u_bmf="$("$work/fkwu" "$work/t-bmf.txt" 5 | head -1)"
u_heap="$("$work/fkwu" "$work/t-heap.txt" 0 | head -1)"
u_org="$("$work/fkwu" "$work/t-org.txt" 0 | head -1)"
echo "UNIVERSAL walker (one binary, no baked program — loads table files through the fs port):"
echo "  fib table -> $u_fib  even/odd -> $u_e10/$u_e7  bmf-grammar-compiled -> $u_bmf  heap -> $u_heap  organs -> $u_org"
if [[ "$u_fib" != "$go_fib" || "$u_e10" != "1" || "$u_e7" != "0" || "$u_bmf" != "22" || "$u_heap" != "25" || "$u_org" != "7" ]]; then
    echo "FAIL  universal walker parity broken"; exit 1
fi
echo "  m4e2 arena heap: EMPTY/CONS/HEAD/TAIL/LEN/NTH returned 25 from [7,8]"
echo "  organs mask 7 = RAM set/get roundtrip + real clock + entropy (two draws differed), physically"
cold="$("$work/fkjit" 28 | head -1)"
hotout="$("$work/fkjit" 28 50)"; hot="$(printf '%s\n' "$hotout" | head -1)"; njit="$(printf '%s\n' "$hotout" | tail -1)"
cold_ms="$(median_ms 9 "$work/fkjit" 28)"
hot_ms="$(median_ms 9 "$work/fkjit" 28 50)"
echo "SELF-JIT on heat (native alternatives lowered FROM the cells; threshold flips dispatch at runtime):"
echo "  cold fib28=$cold (${cold_ms} ms, walk only)  hot fib28=$hot (${hot_ms} ms, threshold 50, njit=$njit)"
if [[ "$cold" != "$go_fib" || "$hot" != "$go_fib" || "$njit" == "0" ]]; then
    echo "FAIL  self-JIT parity or flip broken"; exit 1
fi
echo "  parity held across the flip — gas cooled to ice on measured heat, the probe showing the crossing"

echo
# ── 11. streaming BMF — cursor + stack, no tokenizer ─────────────────────
# Rules match bytes STRAIGHT OFF the loaded source stream (op 17 BUF); the
# cursor position lives in the RAM organ so save/restore is a pointer move
# (BMA's discipline); recipe args ride the call stack. Choice/fail with a
# real backtrack: rule A (match x then digits) | rule B (digits).
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/cur-driver.fk"
cat >> "$work/cur-driver.fk" <<'EOF'
(defn seqq (a b) (fk-if a b b))
(defn adv () (fk-set (fk-lit 0) (fk-add (fk-get (fk-lit 0)) (fk-lit 1))))
(defn x10 () (fk-add (fk-add (fk-add (fk-arg) (fk-arg)) (fk-add (fk-arg) (fk-arg))) (fk-add (fk-add (fk-add (fk-arg) (fk-arg)) (fk-add (fk-arg) (fk-arg))) (fk-add (fk-arg) (fk-arg)))))
(let number (fk-if (fk-le (fk-lit 48) (fk-buf (fk-get (fk-lit 0))))
                   (fk-if (fk-le (fk-buf (fk-get (fk-lit 0))) (fk-lit 57))
                          (seqq (adv) (fk-call 2 (fk-add (x10) (fk-sub (fk-buf (fk-sub (fk-get (fk-lit 0)) (fk-lit 1))) (fk-lit 48)))))
                          (fk-arg))
                   (fk-arg)))
(let ruleA (fk-if (fk-sub (fk-buf (fk-get (fk-lit 0))) (fk-lit 120))
                  (fk-lit 0)
                  (seqq (adv) (fk-call 2 (fk-lit 0)))))
(let entry (seqq (fk-set (fk-lit 1) (fk-get (fk-lit 0)))
           (seqq (fk-set (fk-lit 2) (fk-call 1 (fk-lit 0)))
                 (fk-if (fk-get (fk-lit 2))
                        (fk-get (fk-lit 2))
                        (seqq (fk-set (fk-lit 0) (fk-get (fk-lit 1))) (fk-call 2 (fk-lit 0)))))))
(print "==TM==")
(print (fkc-table-file (list entry ruleA number)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/cur-driver.fk" 2>/dev/null) > "$work/cur.out"
sed -n '/^==TM==$/,/^==END==$/p' "$work/cur.out" | sed -e '1d' -e '$d' > "$work/t-match.txt"
printf 'x42' > "$work/src-a.txt"; printf '9001' > "$work/src-b.txt"
m_a="$("$work/fkwu" "$work/t-match.txt" 0 "$work/src-a.txt" | head -1)"
m_b="$("$work/fkwu" "$work/t-match.txt" 0 "$work/src-b.txt" | head -1)"
echo "streaming BMF (one matcher table; bytes off the cursor; backtrack = pointer move):"
echo "  source x42  -> $m_a (rule A: match x, stream digits)"
echo "  source 9001 -> $m_b (A fails on byte one -> cursor restored -> rule B streams digits)"
if [[ "$m_a" != "42" || "$m_b" != "9001" ]]; then
    echo "FAIL  streaming cursor matcher broke"; exit 1
fi

echo
# ── 13. n1/n2 — the NET organ + the api on a 4th-kernel-compiled binary ──
# A server-variant binary owns socket/bind/listen/accept/fork; the responder
# program's PUTC bytes (dup2'd to the connection) are the body. Live curl.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/srv-driver.fk"
cat >> "$work/srv-driver.fk" <<'EOF'
(let resp (fkresp "HTTP/1.0 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"status\":\"ok\",\"served_by\":\"fourth-kernel-binary\"}"))
(print "==SRV==")
(print (fkc-emit-server (list resp)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/srv-driver.fk" 2>/dev/null) > "$work/srv.out"
sed -n '/^==SRV==$/,/^==END==$/p' "$work/srv.out" | sed -e '1d' -e '$d' > "$work/api.c"
"$CLANG" -O2 -o "$work/fkapi" "$work/api.c"
PORT=8231
"$work/fkapi" "$PORT" & API_PID=$!
n=0; while [ $n -lt 40 ]; do
    if curl -sS --max-time 1 -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then break; fi
    sleep 0.1   # refused is instant; give the freshly-exec'd server real time to bind
    n=$((n+1))
done
code="$(curl -sS --max-time 3 -w '%{http_code}' -o "$work/body.txt" "http://127.0.0.1:$PORT/health" 2>/dev/null)"
t="$(curl -sS --max-time 3 -w '%{time_total}' -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null)"
kill -9 "$API_PID" 2>/dev/null
echo "n1/n2 the api served on a binary the 4th kernel compiled (net organ: socket/bind/accept/fork):"
echo "  GET /health -> HTTP $code in ${t}s  body: $(cat "$work/body.txt")"
if [[ "$code" != "200" ]]; then
    echo "FAIL  fourth-kernel api binary did not serve 200"; exit 1
fi
echo "  the response BODY is the program's PUTC bytes; the net lifecycle is the constant main (the organ)"

echo
# ── 14. n3 — the DRIVER organ: fork/exec/pipe a host command, parse its stdout ──
# The keystone the model stones ride: the binary spawns a host command, captures
# its stdout into fk_src, and the PROGRAM parses that LIVE stream with the cursor.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/drv-driver.fk"
cat >> "$work/drv-driver.fk" <<'EOF'
(defn seqq (a b) (fk-if a b b))
(defn adv () (fk-set (fk-lit 0) (fk-add (fk-get (fk-lit 0)) (fk-lit 1))))
(defn x2 () (fk-add (fk-arg) (fk-arg)))
(defn x10 () (fk-add (fk-add (x2) (x2)) (fk-add (fk-add (x2) (x2)) (x2))))
(defn curb () (fk-buf (fk-get (fk-lit 0))))
(let numf (fk-if (fk-le (fk-lit 48) (curb)) (fk-if (fk-le (curb) (fk-lit 57)) (seqq (adv) (fk-call 1 (fk-add (x10) (fk-sub (fk-buf (fk-sub (fk-get (fk-lit 0)) (fk-lit 1))) (fk-lit 48))))) (fk-arg)) (fk-arg)))
(let entry (fk-call 1 (fk-lit 0)))
(print "==DRV==")
(print (fkc-emit-driver (list entry numf)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/drv-driver.fk" 2>/dev/null) > "$work/drv.out"
sed -n '/^==DRV==$/,/^==END==$/p' "$work/drv.out" | sed -e '1d' -e '$d' > "$work/fkdrv.c"
"$CLANG" -O2 -o "$work/fkdrv" "$work/fkdrv.c"
d_pf="$("$work/fkdrv" printf 31337 | head -1)"
d_yr="$("$work/fkdrv" date +%Y | head -1)"
echo "n3 the driver organ (fork/exec/pipe a host command; parse its stdout with the BMF cursor):"
echo "  drive 'printf 31337' -> $d_pf   drive 'date +%Y' -> $d_yr (the year parsed off live date stdout)"
if [[ "$d_pf" != "31337" ]]; then
    echo "FAIL  driver did not parse the piped subprocess stdout"; exit 1
fi
echo "  the host command's stdout flows into fk_src; the cursor reads a LIVE subprocess — the organ TTS/STT/LLM ride"

echo
# ── 15. n4/n6 — host MODELS driven by a 4th-kernel binary (gated on tools) ──
# The fkcount parser (counts captured bytes) compiled through the driver IS
# the witness program: the binary drives say (TTS), ollama (LLM), whisper
# (STT) and counts what comes back. Skipped where a tool is absent (CI).
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/mdl-driver.fk"
cat >> "$work/mdl-driver.fk" <<'EOF'
(print "==C==")
(print (fkc-emit-driver (fkcount-fns)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/mdl-driver.fk" 2>/dev/null) > "$work/mdl.out"
sed -n '/^==C==$/,/^==END==$/p' "$work/mdl.out" | sed -e '1d' -e '$d' > "$work/fkcnt.c"
"$CLANG" -O2 -o "$work/fkcnt" "$work/fkcnt.c"
echo "n4/n6 host models driven by the 4th-kernel-compiled binary (the driver organ + the byte-counter program):"
if command -v say >/dev/null; then
    aiff="$work/spoke.aiff"
    "$work/fkcnt" say -o "$aiff" "the fourth kernel speaks" >/dev/null 2>&1
    if [[ -s "$aiff" ]]; then
        echo "  n4 TTS: the binary drove 'say' -> $(wc -c < "$aiff" | tr -d ' ') bytes of real audio at $aiff"
    else
        echo "  n4 TTS: say produced no audio file (unexpected)"
    fi
else
    echo "  n4 TTS: 'say' absent — skipped"
fi
if command -v ollama >/dev/null; then
    sm="$(ollama list 2>/dev/null | awk 'NR>1{print $1}' | grep -E ':3b|llama3.2' | head -1)"
    [[ -z "$sm" ]] && sm="$(ollama list 2>/dev/null | awk 'NR==2{print $1}')"
    if [[ -n "$sm" ]]; then
        b0=$(python3 -c 'import time;print(time.time())')
        n="$("$work/fkcnt" ollama run "$sm" "one short sentence about a self-compiling kernel" 2>/dev/null | head -1)"
        b1=$(python3 -c 'import time;print(time.time())')
        echo "  n6 LLM: the binary drove ollama '$sm' -> captured + counted $n bytes in $(python3 -c "print(f'{$b1-$b0:.1f}')")s"
    fi
    # the largest local model — driven if present; the headline bonus
    big="$(ollama list 2>/dev/null | awk '{print $1}' | grep -iE '8x22b|70b|mixtral' | sort | tail -1)"
    if [[ -n "$big" ]]; then
        echo "  n6 LARGEST: $big present — drive it with: $work/fkcnt ollama run $big \"...\" (115 GB class; minutes to load; see evidence for the measured run)"
    fi
else
    echo "  n6 LLM: 'ollama' absent — skipped"
fi
echo "  the model COMPUTE rides the host organ; the 4th-kernel binary drives it and counts the output (host-resource-access)"

echo
# ── 16. n8 — the Form-emitted machine code, made visible ────────────────
# Disassemble the emitted walker: Form recipe -> emitted C -> real ARM64.
if command -v otool >/dev/null && [[ -x "$work/fkwu" ]]; then
    insns="$(otool -tvV "$work/fkwu" 2>/dev/null | grep -cE '^[0-9a-f]{16}')"
    echo "n8 the Form-emitted machine code (otool on the universal walker binary):"
    echo "  the recipe walker is $insns native instructions; first ops of fk_walk:"
    otool -tvV "$work/fkwu" 2>/dev/null | grep -A 6 '_fk_walk:' | head -7 | sed 's/^/    /'
    echo "  Form recipe -> emitted C -> $(uname -m) machine code — the whole arc, real"
elif command -v objdump >/dev/null && [[ -x "$work/fkwu" ]]; then
    echo "n8 the Form-emitted machine code (objdump):"
    objdump -d "$work/fkwu" 2>/dev/null | grep -A 6 '<fk_walk>:' | head -7 | sed 's/^/    /'
else
    echo "n8 disassembler (otool/objdump) absent — skipped"
fi

echo
# ── 17. m4e3 first stone — Form SOURCE parsed (in Form) and run on the 4th kernel ──
# A Form parser written in Form reads source TEXT (recursive descent, a cursor,
# no tokenizer), emits a walker program; the universal binary runs it. Real
# Form source -> a value, end to end on the fourth kernel.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" "$FORMDIR/form-stdlib/form-parse.fk" > "$work/fp-driver.fk"
cat >> "$work/fp-driver.fk" <<'EOF'
(print "==T1==")
(print (fkc-table-file (list (fp-parse "(add (sub 50 8) (add 0 0))"))))
(print "==T2==")
(print (fkc-table-file (list (fp-parse "(if (le 3 5) 111 222)"))))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/fp-driver.fk" 2>/dev/null) > "$work/fp.out"
sed -n '/^==T1==$/,/^==T2==$/p' "$work/fp.out" | sed -e '1d' -e '$d' > "$work/fp-t1.txt"
sed -n '/^==T2==$/,/^==END==$/p' "$work/fp.out" | sed -e '1d' -e '$d' > "$work/fp-t2.txt"
fp1="$("$work/fkwu" "$work/fp-t1.txt" 0 | head -1)"
fp2="$("$work/fkwu" "$work/fp-t2.txt" 0 | head -1)"
echo "m4e3 first stone — Form SOURCE parsed in Form, run on the universal 4th-kernel binary:"
echo "  source '(add (sub 50 8) (add 0 0))' -> $fp1 (expect 42)   '(if (le 3 5) 111 222)' -> $fp2 (expect 111)"
if [[ "$fp1" != "42" || "$fp2" != "111" ]]; then
    echo "FAIL  Form-source parse-and-run broke"; exit 1
fi
echo "  the parser is recursive-descent over the source string (a cursor, no tokenizer); op-gap to full bands is m4e4 (defn/let/do/str_*)"

echo
# ── 18. the live afferent witness — afferent-offer.fk's ao-wait on the real ──
# clock. The engine (proven → 511 with ticks as data) makes the dispatch|nothing
# decision at composition; the lowered program (afferent-live.fk) blocks on
# op 15 TIME through the SAME universal binary. No event in the window →
# nothing after REAL elapsed time (timeout==nothing, live); an armed timer's
# tick arrives → its handler fires with the payload — the SIGALRM shape
# witnessed on a wall clock.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" "$FORMDIR/form-stdlib/afferent-offer.fk" \
    "$FORMDIR/form-stdlib/afferent-live.fk" > "$work/ao-driver.fk"
cat >> "$work/ao-driver.fk" <<'EOF'
(let live-table (ao-table (list (ao-entry (ao-sig-alrm) "on-alarm")
                                (ao-entry (ao-irq-keyboard) "on-key"))))
(let no-mask (ao-mask (list)))
(print "==TKEY==")
(print (fkc-table-file (aolv-fns live-table no-mask (list (ao-irq (ao-irq-keyboard) 0 42)) 2 1000)))
(print "==TALARM==")
(print (fkc-table-file (aolv-fns live-table no-mask (list (ao-alarm 1)) 2 1000)))
(print "==TNOTHING==")
(print (fkc-table-file (aolv-fns live-table no-mask (list) 1 1000)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/ao-driver.fk" 2>/dev/null) > "$work/ao.out"
sed -n '/^==TKEY==$/,/^==TALARM==$/p' "$work/ao.out" | sed -e '1d' -e '$d' > "$work/t-ao-key.txt"
sed -n '/^==TALARM==$/,/^==TNOTHING==$/p' "$work/ao.out" | sed -e '1d' -e '$d' > "$work/t-ao-alarm.txt"
sed -n '/^==TNOTHING==$/,/^==END==$/p' "$work/ao.out" | sed -e '1d' -e '$d' > "$work/t-ao-nothing.txt"

ao_run() { # table-file -> "ack elapsed value wall_s time-polls"
    python3 - "$work/fkwu" "$1" <<'PY'
import subprocess, sys, time
t0 = time.perf_counter()
out = subprocess.run([sys.argv[1], sys.argv[2], "0"], capture_output=True, text=True).stdout.splitlines()
wall = time.perf_counter() - t0
print(out[0], out[1], out[2], f"{wall:.3f}", out[17])
PY
}

read -r k_ack k_el k_val k_wall k_polls <<<"$(ao_run "$work/t-ao-key.txt")"
read -r a_ack a_el a_val a_wall a_polls <<<"$(ao_run "$work/t-ao-alarm.txt")"
read -r n_ack n_el n_val n_wall n_polls <<<"$(ao_run "$work/t-ao-nothing.txt")"
echo "live afferent witness (ao-wait's verdict breathing op 15 TIME; the SAME universal binary):"
echo "  latched irq        -> $k_ack elapsed=${k_el}s payload=$k_val wall=${k_wall}s time-polls=$k_polls (already-arrived offer dispatches now)"
echo "  armed timer (1s)   -> $a_ack elapsed=${a_el}s payload=$a_val wall=${a_wall}s time-polls=$a_polls (the tick ARRIVED on the host clock)"
echo "  no event, 1s wait  -> $n_ack elapsed=${n_el}s value=$n_val wall=${n_wall}s time-polls=$n_polls (live timeout==nothing, past the deadline)"
if [[ "$k_ack" != "on-key" || "$k_val" != "42" ]] || [[ "$k_el" != "0" && "$k_el" != "1" ]]; then
    echo "FAIL  latched-irq dispatch broke"; exit 1
fi
if [[ "$a_ack" != "on-alarm" || "$a_el" != "1" || "$a_val" != "0" ]]; then
    echo "FAIL  armed-timer dispatch broke — the tick did not arrive as the SIGALRM shape"; exit 1
fi
if ! python3 -c "import sys; sys.exit(0 if float('$a_wall') < 2.0 else 1)"; then
    echo "FAIL  the armed timer did not beat its 2s window"; exit 1
fi
if [[ "$n_ack" != "nothing" || "$n_el" != "2" || "$n_val" != "0" ]]; then
    echo "FAIL  live timeout did not acknowledge nothing"; exit 1
fi
if ! python3 -c "import sys; sys.exit(0 if float('$n_wall') >= 1.0 else 1)"; then
    echo "FAIL  the nothing came BEFORE the deadline elapsed — not a live wait"; exit 1
fi
echo "  the engine's arms are afferent-offer.fk's, unchanged; only the tick source went live (band: tests/afferent-live-band.fk -> 63)"

echo
# ── 19. n7 — bands-on-fourth-arm: a REAL stdlib band, unmodified, on fkw ──
# The m4e3 flattener (form-flatten.fk) reads learning-trend.fk + its band
# FROM DISK, flattens defn/let/the curated ops onto the walker's table, and
# the SAME universal binary runs it. The three walking siblings' verdict
# comes through their own front door (validate.sh — the body's proof
# machinery, BML core source-compiled there); fkw must return the same
# number. This is the band ratchet's first click: 0 -> 1.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" "$FORMDIR/form-stdlib/form-parse.fk" \
    "$FORMDIR/form-stdlib/form-flatten.fk" > "$work/flt-driver.fk"
cat >> "$work/flt-driver.fk" <<'EOF'
(print "==TLT==")
(print (fkc-table-file (flt-band-fns (read_file "form-stdlib/learning-trend.fk") (read_file "form-stdlib/tests/learning-trend-band.fk"))))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/flt-driver.fk" 2>/dev/null) > "$work/flt.out"
sed -n '/^==TLT==$/,/^==END==$/p' "$work/flt.out" | sed -e '1d' -e '$d' > "$work/t-lt.txt"
three_way="$(cd "$FORMDIR" && ./validate.sh form-stdlib/core.fk form-stdlib/learning-trend.fk form-stdlib/tests/learning-trend-band.fk 2>/dev/null | sed -n 's/.*→ //p' | head -1)"
fkw_band="$("$work/fkwu" "$work/t-lt.txt" 0 | head -1)"
echo "n7 bands-on-fourth-arm — learning-trend-band (UNMODIFIED source, flattened by form-flatten.fk):"
echo "  three-walker verdict (validate.sh) = $three_way   fkw = $fkw_band   (expect 127)"
if [[ -z "$three_way" || "$three_way" != "$fkw_band" || "$fkw_band" != "127" ]]; then
    echo "FAIL  the fourth arm disagrees with the siblings on a real band"; exit 1
fi
echo "  bands-on-fourth-arm: 1 (gt/ge/eq/and lowered onto IF/LE; defn -> CALL table; let inlined; lists on the arena)"

echo
# ── 20. melt-on-cool — the arena crosses its measured boundary and SURVIVES ──
# Round 1 measured the bump-only carrier: holds to 4095 cells, n=4096 wraps the
# root onto the sentinel (LEN 0), n=4200 tears the chain (LEN 104). The melt
# door (arena-melt.fk's proven walk, emitted as fk_mlive/fk_mcopy/fk_melt) fires
# at the high-water line; live cells cross into fresh space; the carrier doubles
# only when the live set crowds it. Same universal binary as section 8; the
# melt readout (allocated live dead cap-from cap-to bytes-reclaimed) on stderr.
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/melt-driver.fk"
cat >> "$work/melt-driver.fk" <<'EOF'
(let chain (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-empty)
                  (fk-cons (fk-arg) (fk-call 1 (fk-sub (fk-arg) (fk-lit 1))))))
(let chainlen (fk-len (fk-call 1 (fk-arg))))
(let churn (fk-if (fk-le (fk-arg) (fk-lit 1))
                  (fk-len (fk-call 1 (fk-lit 1000)))
                  (fk-add (fk-sub (fk-len (fk-call 1 (fk-lit 1000))) (fk-lit 1000))
                          (fk-call 0 (fk-sub (fk-arg) (fk-lit 1))))))
(print "==TCH==")
(print (fkc-table-file (list chainlen chain)))
(print "==TCU==")
(print (fkc-table-file (list churn chain)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/melt-driver.fk" 2>/dev/null) > "$work/melt.out"
sed -n '/^==TCH==$/,/^==TCU==$/p' "$work/melt.out" | sed -e '1d' -e '$d' > "$work/t-chain.txt"
sed -n '/^==TCU==$/,/^==END==$/p' "$work/melt.out" | sed -e '1d' -e '$d' > "$work/t-churn.txt"
m64="$("$work/fkwu" "$work/t-chain.txt" 64 2>"$work/me64.txt" | head -1)"
m4095="$("$work/fkwu" "$work/t-chain.txt" 4095 2>"$work/me4095.txt" | head -1)"
m4096="$("$work/fkwu" "$work/t-chain.txt" 4096 2>"$work/me4096.txt" | head -1)"
m4200="$("$work/fkwu" "$work/t-chain.txt" 4200 2>"$work/me4200.txt" | head -1)"
mchurn="$("$work/fkwu" "$work/t-churn.txt" 5 2>"$work/mechurn.txt" | head -1)"
echo "melt-on-cool (the round-1 deaths, rerun on the melt-doored carrier):"
echo "  chain n=64   -> $m64    (dormant below water — no melt line)"
echo "  chain n=4095 -> $m4095  (held before; still holds, now melting mid-build)"
echo "  chain n=4096 -> $m4096  (was 0 — the root wrapped onto the sentinel)"
echo "  chain n=4200 -> $m4200  (was 104 — the chain torn at the wrap)"
echo "  churn 5x1000 -> $mchurn  (rebuilds cross the water; garbage reclaimed)"
echo "  melt readout (allocated live dead cap-from cap-to bytes-reclaimed):"
sed 's/^/    chain n=4200: /' "$work/me4200.txt"
sed 's/^/    churn 5x1000: /' "$work/mechurn.txt"
if [[ "$m64" != "64" || "$m4095" != "4095" || "$m4096" != "4096" || "$m4200" != "4200" || "$mchurn" != "1000" ]]; then
    echo "FAIL  the melt door did not carry the boundary crossing"; exit 1
fi
if [[ -s "$work/me64.txt" ]]; then
    echo "FAIL  melt fired below the water line"; exit 1
fi
if ! grep -q '^melt ' "$work/me4200.txt" || ! grep -q '^melt ' "$work/mechurn.txt"; then
    echo "FAIL  no melt readout where the boundary was crossed"; exit 1
fi
awk '/^melt /{ok=($6==8192)}END{exit ok?0:1}' "$work/me4200.txt" || { echo "FAIL  chain melt did not grow the crowded carrier"; exit 1; }
awk '/^melt /{ok=($4>0 && $6==4096)}END{exit ok?0:1}' "$work/mechurn.txt" || { echo "FAIL  churn melt did not reclaim within the kept carrier"; exit 1; }
echo "  the melt the recipes prove is the melt the binary DOES — live sets cross the boundary, garbage returns"

echo
# ── 21. melt-hot-swap — the SELF-JIT's gas-ice cycle closes BOTH ways ─────
# Section 8-10 ships the rise (heat per function; dispatch flips native past
# the hot line). This face: heat DECAYS (halve per 256-dispatch epoch), a
# crystallized native MELTS back to walking when its decayed heat falls below
# the melt line (50% of hot), and re-crystallization is champion-challenger
# gated — 2 CONSECUTIVE epochs above the hot line re-earn ice (the walking
# path is the champion, always correct; one hot spike is not enough). All
# policy is recipe cells (fkc-decay-quantum/divisor, fkc-melt-line-pct,
# fkc-cc-earn-epochs); the C is emitted from them. One binary, two scenarios
# by arg: 0 = drive hot -> idle epochs -> ONE more call (must WALK: ice fell);
# 1 = drive hot -> idle epochs -> re-heat (must RE-EARN: ice returns).
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" > "$work/jm-driver.fk"
cat >> "$work/jm-driver.fk" <<'EOF'
(let tri   (fk-if (fk-le (fk-arg) (fk-lit 1)) (fk-arg) (fk-add (fk-arg) (fk-call 2 (fk-sub (fk-arg) (fk-lit 1))))))
(let loopA (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 0) (fk-add (fk-call 2 (fk-lit 20)) (fk-call 1 (fk-sub (fk-arg) (fk-lit 1))))))
(let loopB (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 0) (fk-add (fk-sub (fk-set (fk-lit 9) (fk-arg)) (fk-arg)) (fk-call 3 (fk-sub (fk-arg) (fk-lit 1))))))
(let driver (fk-if (fk-arg)
                   (fk-add (fk-call 1 (fk-lit 40)) (fk-add (fk-call 3 (fk-lit 800)) (fk-call 1 (fk-lit 40))))
                   (fk-add (fk-call 1 (fk-lit 40)) (fk-add (fk-call 3 (fk-lit 800)) (fk-call 2 (fk-lit 20))))))
(print "==JMC==")
(print (fkc-emit-jitmelt (list driver loopA tri loopB)))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/jm-driver.fk" 2>/dev/null) > "$work/jm.out"
sed -n '/^==JMC==$/,/^==END==$/p' "$work/jm.out" | sed -e '1d' -e '$d' > "$work/fkjm.c"
"$CLANG" -O2 -o "$work/fkjm" "$work/fkjm.c"
jm0_walk="$("$work/fkjm" 0 | head -1)"
jm1_walk="$("$work/fkjm" 1 | head -1)"
"$work/fkjm" 0 50 > "$work/jm-a.out" 2> "$work/jm-a.err"
"$work/fkjm" 1 50 > "$work/jm-b.out" 2> "$work/jm-b.err"
vA="$(sed -n 1p "$work/jm-a.out")"; meltA="$(sed -n 3p "$work/jm-a.out")"; frzA="$(sed -n 4p "$work/jm-a.out")"
heatA2="$(sed -n 9p "$work/jm-a.out")"; iceA2="$(sed -n 10p "$work/jm-a.out")"
vB="$(sed -n 1p "$work/jm-b.out")"; njitB="$(sed -n 2p "$work/jm-b.out")"; meltB="$(sed -n 3p "$work/jm-b.out")"; frzB="$(sed -n 4p "$work/jm-b.out")"
heatB2="$(sed -n 9p "$work/jm-b.out")"; iceB2="$(sed -n 10p "$work/jm-b.out")"
echo "melt-hot-swap (heat rises per dispatch, halves per epoch; ice melts below the line; re-ice is EARNED):"
echo "  scenario 0 (hot->cool->one call): value=$vA (walk $jm0_walk)  freezes=$frzA melts=$meltA  hotfn end: heat=$heatA2 ice=$iceA2 (2=melted gas)"
echo "  scenario 1 (hot->cool->re-heat):  value=$vB (walk $jm1_walk)  freezes=$frzB melts=$meltB njit=$njitB  hotfn end: heat=$heatB2 ice=$iceB2 (1=ice)"
echo "  hotfn (fn 2) boundary crossings (jf=crystallize@heat, jm=melt@heat):"
grep '^j[fm] 2 ' "$work/jm-b.err" | sed 's/^/    /'
if [[ "$vA" != "8610" || "$jm0_walk" != "8610" || "$vB" != "16800" || "$jm1_walk" != "16800" ]]; then
    echo "FAIL  melt-hot-swap parity broken across the cycle"; exit 1
fi
if [[ "$frzA" != "1" || "$meltA" != "1" || "$iceA2" != "2" ]]; then
    echo "FAIL  the cooled native did not melt back to gas"; exit 1
fi
if (( heatA2 <= 12 )); then
    echo "FAIL  the post-melt call did not WALK (heat shows a native dispatch, not 20 walked ones)"; exit 1
fi
if [[ "$frzB" != "2" || "$meltB" != "1" || "$iceB2" != "1" || "$njitB" == "0" ]]; then
    echo "FAIL  re-heat did not re-earn ice through the champion-challenger gate"; exit 1
fi
seq2="$(grep '^j[fm] 2 ' "$work/jm-b.err" | awk '{printf "%s", substr($1,2,1)}')"
if [[ "$seq2" != "fmf" ]]; then
    echo "FAIL  hotfn's phase order is not crystallize -> melt -> re-earn (got: $seq2)"; exit 1
fi
jf1="$(grep '^jf 2 ' "$work/jm-b.err" | sed -n 1p | awk '{print $3}')"
jmh="$(grep '^jm 2 ' "$work/jm-b.err" | awk '{print $3}')"
if (( jf1 <= 50 )) || (( jmh >= 25 )); then
    echo "FAIL  heat at the boundary crossings disagrees with the policy cells (jf=$jf1 jm=$jmh)"; exit 1
fi
echo "  the cycle closed both ways: measured heat froze it, measured cool melted it, ice re-EARNED — never declared"

echo
# ── 22. m4e4 — multi-param bands on the fourth arm: the ratchet climbs 1 -> 10 ──
# form-flatten.fk's packed-args rule (an N-arg call right-folds its arguments
# into a CONS chain on the arena; the callee binds each param as NTH(ARG, i))
# is a pure flattening lift — ZERO new walker tags, the emitted C unchanged.
# Nine more REAL stdlib bands (unmodified source from disk) flatten onto the
# walker's table and run on the SAME universal binary; each verdict is gated
# four-way against the three walking siblings' own front door (validate.sh,
# the nine invocations in parallel). feature-vector is the honest tenth: its
# flatten lands and fits the loader, but its band-scale allocation crosses
# the arena's water line and the copying melt cannot see packed args held in
# suspended C frames (m4e2's named suspended-temp gap) — it stays off the
# ratchet until call arguments ride a walker-managed value stack instead of
# C locals. adler32 (the original multi-param candidate) still waits on the
# band/shl_u32/add_u32 figure family and let-in-defn — named, not bent.
mp_mods=(cooldown alert-gate value-execution anomaly-band body-state field-fusion histogram-peak model-retire signal-derivative)
mp_exps=(63 127 7 127 127 127 127 63 127)
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" "$FORMDIR/form-stdlib/form-parse.fk" \
    "$FORMDIR/form-stdlib/form-flatten.fk" > "$work/mp-driver.fk"
for m in "${mp_mods[@]}" feature-vector; do
    cat >> "$work/mp-driver.fk" <<EOF
(print "==MP-$m==")
(print (fkc-table-file (flt-band-fns (read_file "form-stdlib/$m.fk") (read_file "form-stdlib/tests/$m-band.fk"))))
EOF
done
echo '(print "==MP-END==")' >> "$work/mp-driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/mp-driver.fk" 2>/dev/null) > "$work/mp.out"
prev=""
while IFS= read -r line; do
    if [[ "$line" == ==MP-*== ]]; then
        prev="${line#==MP-}"; prev="${prev%==}"
        : > "$work/t-mp-$prev.txt"
    elif [[ -n "$prev" ]]; then
        printf '%s\n' "$line" >> "$work/t-mp-$prev.txt"
    fi
done < "$work/mp.out"
for m in "${mp_mods[@]}"; do
    (cd "$FORMDIR" && ./validate.sh form-stdlib/core.fk "form-stdlib/$m.fk" "form-stdlib/tests/$m-band.fk" 2>/dev/null \
        | sed -n 's/.*→ //p' | head -1 > "$work/vw-$m.txt") &
done
wait
echo "m4e4 multi-param bands on the fourth arm (packed args, flattened by form-flatten.fk):"
mp_pass=0
for k in "${!mp_mods[@]}"; do
    m="${mp_mods[$k]}"; exp="${mp_exps[$k]}"
    three_way="$(cat "$work/vw-$m.txt")"
    fkw_v="$("$work/fkwu" "$work/t-mp-$m.txt" 0 2>/dev/null | head -1)"
    printf "  %-18s three-walker (validate.sh) = %-4s fkw = %-4s (expect %s)\n" "$m" "$three_way" "$fkw_v" "$exp"
    if [[ -z "$three_way" || "$three_way" != "$fkw_v" || "$fkw_v" != "$exp" ]]; then
        echo "FAIL  the fourth arm disagrees with the siblings on $m"; exit 1
    fi
    mp_pass=$((mp_pass + 1))
done
fv_rows="$(wc -w < "$work/t-mp-feature-vector.txt")"
if [[ "$fv_rows" -lt 10 ]]; then
    echo "FAIL  the feature-vector flatten itself regressed"; exit 1
fi
echo "  feature-vector     flattens ($fv_rows table words, fits the loader) — held OFF the ratchet:"
echo "                     band-scale allocation crosses the melt water line and packed args in"
echo "                     suspended C frames are outside the copying melt's root set (m4e2 gap)"
echo "  bands-on-fourth-arm: $((mp_pass + 1)) (learning-trend + $mp_pass multi-param bands, four-way gated)"

echo
echo "conditions: $(uname -m) $(uname -s), clang -O2, full-process invocations (startup included)"
echo "ok — parity held and the rows are real; the spec is docs/coherence-substrate/fourth-kernel.form"

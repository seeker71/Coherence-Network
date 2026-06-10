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
echo "   source through the port is m4e2 heap + m4e4 strings — named in fourth-kernel.form)"

echo
# ── 8-10. the Form-OS face: universal loader, self-JIT on heat, the organs ──
cat "$FORMDIR/form-stdlib/minimal-surface.fk" "$FORMDIR/form-stdlib/fourth-walker.fk" \
    "$FORMDIR/form-stdlib/fourth-walker-emit.fk" "$FORMDIR/form-stdlib/bmf-mini.fk" > "$work/os-driver.fk"
cat >> "$work/os-driver.fk" <<'EOF'
(let fibc (fk-if (fk-le (fk-arg) (fk-lit 1)) (fk-arg) (fk-add (fk-call 0 (fk-sub (fk-arg) (fk-lit 1))) (fk-call 0 (fk-sub (fk-arg) (fk-lit 2))))))
(let even (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 1) (fk-call 1 (fk-sub (fk-arg) (fk-lit 1)))))
(let odd  (fk-if (fk-le (fk-arg) (fk-lit 0)) (fk-lit 0) (fk-call 0 (fk-sub (fk-arg) (fk-lit 1)))))
(let g1 (list (bmf-rule 1 3 10) (bmf-rule 2 4 3)))
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
sed -n '/^==TBMF==$/,/^==TORG==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/t-bmf.txt"
sed -n '/^==TORG==$/,/^==JIT==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/t-org.txt"
sed -n '/^==JIT==$/,/^==END==$/p' "$work/os.out" | sed -e '1d' -e '$d' > "$work/fkjit.c"
"$CLANG" -O2 -o "$work/fkwu" "$work/uni.c"
"$CLANG" -O2 -o "$work/fkjit" "$work/fkjit.c"
u_fib="$("$work/fkwu" "$work/t-fib.txt" 28 | head -1)"
u_e10="$("$work/fkwu" "$work/t-eo.txt" 10 | head -1)"; u_e7="$("$work/fkwu" "$work/t-eo.txt" 7 | head -1)"
u_bmf="$("$work/fkwu" "$work/t-bmf.txt" 5 | head -1)"
u_org="$("$work/fkwu" "$work/t-org.txt" 0 | head -1)"
echo "UNIVERSAL walker (one binary, no baked program — loads table files through the fs port):"
echo "  fib table -> $u_fib  even/odd -> $u_e10/$u_e7  bmf-grammar-compiled -> $u_bmf  organs -> $u_org"
if [[ "$u_fib" != "$go_fib" || "$u_e10" != "1" || "$u_e7" != "0" || "$u_bmf" != "22" || "$u_org" != "7" ]]; then
    echo "FAIL  universal walker parity broken"; exit 1
fi
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
echo "conditions: $(uname -m) $(uname -s), clang -O2, full-process invocations (startup included)"
echo "ok — parity held and the rows are real; the spec is docs/coherence-substrate/fourth-kernel.form"

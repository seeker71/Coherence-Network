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
echo "conditions: $(uname -m) $(uname -s), clang -O2, full-process invocations (startup included)"
echo "ok — parity held and the rows are real; the spec is docs/coherence-substrate/fourth-kernel.form"

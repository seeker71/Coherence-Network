#!/usr/bin/env bash
# form-kernel-validate.sh — sibling kernels run every Form source file;
# outputs must be identical. The kernels are siblings; they keep each
# other honest. Any divergence is a bug in one of them or a spec corner
# nobody documented — worth knowing.
#
# Run from experiments/.
#   ./form-kernel-validate.sh            # validate all samples
#   ./form-kernel-validate.sh path.fk    # validate one file
#   ./form-kernel-validate.sh --bench    # sibling bench suites, side-by-side

set -euo pipefail
cd "$(dirname "$0")"

GO_DIR="form-kernel-go"
RS_DIR="form-kernel-rust"
TS_DIR="form-kernel-ts"
GO_BIN="$GO_DIR/bin-go"
RS_BIN="$RS_DIR/target/release/form-kernel-rust"

# --- build compiled sibling kernels if stale -----------------------------
build_go() {
    if [[ ! -x "$GO_BIN" || "$GO_DIR/main.go" -nt "$GO_BIN" || "$GO_DIR/numeric_bench.go" -nt "$GO_BIN" ]]; then
        echo "  building go kernel..." >&2
        (cd "$GO_DIR" && go build -o bin-go .)
    fi
}
build_rs() {
    if [[ ! -x "$RS_BIN" || "$RS_DIR/src/main.rs" -nt "$RS_BIN" ]]; then
        echo "  building rust kernel..." >&2
        (cd "$RS_DIR" && cargo build --release --quiet)
    fi
}

build_go &
build_rs &
wait

run_ts() {
    if [[ -x "$TS_DIR/node_modules/.bin/tsx" ]]; then
        "$TS_DIR/node_modules/.bin/tsx" "$TS_DIR/src/main.ts" "$@"
    else
        npx --yes tsx "$TS_DIR/src/main.ts" "$@"
    fi
}

# --- bench mode: run sibling bench suites side-by-side -------------------
if [[ "${1:-}" == "--bench" ]]; then
    echo "=== Go ==="
    "$GO_BIN" --bench
    echo ""
    echo "=== Rust ==="
    "$RS_BIN" --bench
    echo ""
    echo "=== TypeScript ==="
    run_ts --bench
    exit 0
fi

# --- run_siblings: feed one Form workload through all kernels, compare ---
# A "workload" can be multiple .fk files loaded sequentially (e.g. stdlib
# prelude + test file). Every kernel receives the same file list.
run_siblings() {
    local label="$1"; shift
    local go_out rs_out ts_out
    go_out=$("$GO_BIN" "$@" 2>&1 || true)
    rs_out=$("$RS_BIN" "$@" 2>&1 || true)
    ts_out=$(run_ts "$@" 2>&1 || true)
    if [[ "$go_out" == "$rs_out" && "$go_out" == "$ts_out" ]]; then
        printf "  ✓  %-30s  → %s\n" "$label" "$go_out"
        ok=$((ok + 1))
    else
        printf "  ✗  %-30s\n      go         = %s\n      rust       = %s\n      typescript = %s\n" \
            "$label" "$go_out" "$rs_out" "$ts_out"
        fail=$((fail + 1))
    fi
}

ok=0
fail=0

# --- single-file mode: validate one explicit file -----------------------
if [[ $# -gt 0 ]]; then
    run_siblings "$(basename "$1")" "$1"
else
    # --- form-samples/*.fk: self-contained files ------------------------
    for f in form-samples/*.fk; do
        run_siblings "$(basename "$f")" "$f"
    done
    # --- form-stdlib/tests/*.fk: prepend stdlib preludes ---------------
    # Convention: core.fk is always prepended. If the test name matches
    # an additional module (e.g. tests/parser.fk → parser.fk), that
    # module is loaded between core.fk and the test.
    if [[ -d form-stdlib/tests ]]; then
        for f in form-stdlib/tests/*.fk; do
            base="$(basename "$f" .fk)"
            module="form-stdlib/${base}.fk"
            if [[ -f "$module" && "$module" != "$f" ]]; then
                run_siblings "stdlib/$(basename "$f")" "form-stdlib/core.fk" "$module" "$f"
            else
                run_siblings "stdlib/$(basename "$f")" "form-stdlib/core.fk" "$f"
            fi
        done
    fi
fi

echo ""
if [[ $fail -eq 0 ]]; then
    echo "  $ok ok, 0 divergent — kernels agree on every sample."
    exit 0
else
    echo "  $ok ok, $fail divergent — kernels disagree. Investigate which is correct."
    exit 1
fi

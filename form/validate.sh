#!/usr/bin/env bash
# validate.sh — sibling kernels run every Form source file;
# outputs must be identical. The kernels are siblings; they keep each
# other honest. Any divergence is a bug in one of them or a spec corner
# nobody documented — worth knowing.
#
# Run from form/.
#   ./validate.sh            # validate all samples
#   ./validate.sh path.fk    # validate one file
#   ./validate.sh prelude.fk test.fk  # validate one workload
#   ./validate.sh --binary  # compile every workload, execute artifacts
#   ./validate.sh --binary prelude.fk test.fk  # compile once, execute artifact
#   ./validate.sh --bench    # sibling bench suites, side-by-side

set -euo pipefail
cd "$(dirname "$0")"

# Keep the kernel-resident bp lookup table in sync with the registry before the
# staleness check decides whether to rebuild. Writes only on change, so a no-op
# run leaves mtimes (and the rebuild decision) untouched.
if command -v python3 >/dev/null 2>&1 && [[ -f ../scripts/gen_bp_table.py ]]; then
    python3 ../scripts/gen_bp_table.py >/dev/null || true
fi

GO_DIR="form-kernel-go"
RS_DIR="form-kernel-rust"
TS_DIR="form-kernel-ts"
GO_BIN="$GO_DIR/bin-go"
RS_BIN="$RS_DIR/target/release/form-kernel-rust"
HOST_STACK_KB="262144"

# --- build compiled sibling kernels if stale -----------------------------
build_go() {
    if [[ ! -x "$GO_BIN" || "$GO_DIR/main.go" -nt "$GO_BIN" || "$GO_DIR/numeric_bench.go" -nt "$GO_BIN" || "$GO_DIR/bp_table.go" -nt "$GO_BIN" ]]; then
        echo "  building go kernel..." >&2
        (cd "$GO_DIR" && go build -o bin-go .)
    fi
}
build_rs() {
    if [[ ! -x "$RS_BIN" || "$RS_DIR/src/main.rs" -nt "$RS_BIN" || "$RS_DIR/src/bp_table.rs" -nt "$RS_BIN" ]]; then
        echo "  building rust kernel..." >&2
        (cd "$RS_DIR" && cargo build --release --quiet)
    fi
}

build_go &
build_rs &
wait

run_ts() {
    local loader="$PWD/$TS_DIR/node_modules/tsx/dist/loader.mjs"
    if [[ -x "$TS_DIR/node_modules/.bin/tsx" ]]; then
        node --stack_size="$HOST_STACK_KB" --import "$loader" "$TS_DIR/src/main.ts" "$@"
    else
        npx --yes tsx --stack_size="$HOST_STACK_KB" "$TS_DIR/src/main.ts" "$@"
    fi
}

source_compile_dir="$(mktemp -d "${TMPDIR:-/tmp}/form-source.XXXXXX")"
mkdir -p form-stdlib/.cache
artifact=""
cleanup() {
    rm -rf "$source_compile_dir"
    if [[ -n "$artifact" ]]; then
        rm -f "$artifact"
    fi
}
trap cleanup EXIT

prepared_args=()
prepare_sources() {
    prepared_args=()
    local src out safe driver
    for src in "$@"; do
        if grep -Eq '^[[:space:]]*section \[' "$src"; then
            safe="${src//\//__}"
            out="$source_compile_dir/$safe"
            driver="$source_compile_dir/compile-${safe}.fk"
            printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$out" > "$driver"
            "$GO_BIN" "form-stdlib/json.fk" "form-stdlib/cache.fk" "form-stdlib/form-ontology-loader.fk" "form-stdlib/line-grammar.fk" "form-stdlib/bmf-core.fk" "form-stdlib/bmf-grammar.fk" "form-stdlib/bml.fk" "form-stdlib/source-compiler.fk" "$driver" >/dev/null
            prepared_args+=("$out")
        else
            prepared_args+=("$src")
        fi
    done
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

binary_mode=0
if [[ "${1:-}" == "--binary" ]]; then
    binary_mode=1
    shift
fi

# --- run_siblings: feed one Form workload through all kernels, compare ---
# A "workload" can be multiple .fk files loaded sequentially (e.g. stdlib
# prelude + test file). Every kernel receives the same file list.
run_siblings() {
    local label="$1"; shift
    local go_out rs_out ts_out
    prepare_sources "$@"
    go_out=$("$GO_BIN" "${prepared_args[@]}" 2>&1 || true)
    rs_out=$("$RS_BIN" "${prepared_args[@]}" 2>&1 || true)
    ts_out=$(run_ts "${prepared_args[@]}" 2>&1 || true)
    if [[ "$go_out" == "$rs_out" && "$go_out" == "$ts_out" ]]; then
        printf "  ✓  %-30s  → %s\n" "$label" "$go_out"
        ok=$((ok + 1))
    else
        printf "  ✗  %-30s\n      go         = %s\n      rust       = %s\n      typescript = %s\n" \
            "$label" "$go_out" "$rs_out" "$ts_out"
        fail=$((fail + 1))
    fi
}

run_siblings_binary() {
    local label="$1"; shift
    local artifact="$1"; shift
    local go_out rs_out ts_out
    go_out=$("$GO_BIN" --binary "$artifact" 2>&1 || true)
    rs_out=$("$RS_BIN" --binary "$artifact" 2>&1 || true)
    ts_out=$(run_ts --binary "$artifact" 2>&1 || true)
    if [[ "$go_out" == "$rs_out" && "$go_out" == "$ts_out" ]]; then
        printf "  ✓  %-30s  → %s\n" "$label" "$go_out"
        ok=$((ok + 1))
    else
        printf "  ✗  %-30s\n      go         = %s\n      rust       = %s\n      typescript = %s\n" \
            "$label" "$go_out" "$rs_out" "$ts_out"
        fail=$((fail + 1))
    fi
}

run_workload() {
    local label="$1"; shift
    local bin_artifact
    if [[ $binary_mode -eq 1 ]]; then
        bin_artifact="$(mktemp "${TMPDIR:-/tmp}/form-kernel.XXXXXX")"
        prepare_sources "$@"
        "$GO_BIN" --emit-binary "$bin_artifact" "${prepared_args[@]}"
        run_siblings_binary "binary/$label" "$bin_artifact"
        rm -f "$bin_artifact"
    else
        run_siblings "$label" "$@"
    fi
}

ok=0
fail=0

# --- explicit mode: validate one file list as one workload --------------
if [[ $# -gt 0 ]]; then
    label=""
    for f in "$@"; do
        base="$(basename "$f")"
        if [[ -z "$label" ]]; then
            label="$base"
        else
            label="$label+$base"
        fi
    done
    run_workload "$label" "$@"
else
    # --- form-samples/*.fk: self-contained files ------------------------
    for f in form-samples/*.fk; do
        run_workload "$(basename "$f")" "$f"
    done
    # --- form-stdlib/tests/*.{fk,form}: prepend stdlib preludes --------
    # Convention: core.fk is always prepended. If the test name matches
    # an additional module (e.g. tests/parser.fk → parser.fk), that
    # module is loaded between core.fk and the test.
    if [[ -d form-stdlib/tests ]]; then
        for f in form-stdlib/tests/*.fk form-stdlib/tests/*.form; do
            if [[ ! -e "$f" ]]; then
                continue
            fi
            base="$(basename "$f")"
            base="${base%.*}"
            module="form-stdlib/${base}.fk"
            # A test file may declare extra preludes via a header line:
            #   ; preludes: form-stdlib/engine.fk form-stdlib/grammar-bnf.fk
            # When present, those modules load between core.fk and the test
            # (in the order declared). The same-name convention still works
            # — modules referenced by the header replace the auto-prepend.
            preludes=$(grep -E '^; preludes:' "$f" 2>/dev/null | head -1 | sed 's/^; preludes://' || true)
            if [[ -n "$preludes" ]]; then
                # shellcheck disable=SC2086
                run_workload "stdlib/$(basename "$f")" "form-stdlib/core.fk" $preludes "$f"
            elif [[ -f "$module" && "$module" != "$f" ]]; then
                run_workload "stdlib/$(basename "$f")" "form-stdlib/core.fk" "$module" "$f"
            else
                run_workload "stdlib/$(basename "$f")" "form-stdlib/core.fk" "$f"
            fi
        done
    fi
fi

echo ""
if [[ $fail -eq 0 ]]; then
    if [[ $binary_mode -eq 1 ]]; then
        echo "  $ok ok, 0 divergent — kernels agree on every binary artifact."
    else
        echo "  $ok ok, 0 divergent — kernels agree on every sample."
    fi
    exit 0
else
    echo "  $ok ok, $fail divergent — kernels disagree. Investigate which is correct."
    exit 1
fi

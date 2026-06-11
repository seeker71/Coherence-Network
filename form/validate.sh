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

# Keep package-manager advisory text out of sibling-kernel output comparison.
# The TypeScript arm may invoke npm/npx when tsx is not locally installed; an
# update notice on stdout makes identical kernel results look divergent.
export NO_UPDATE_NOTIFIER=1
export NPM_CONFIG_UPDATE_NOTIFIER=false
export npm_config_update_notifier=false

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
    if [[ ! -x "$GO_BIN" ]] || find "$GO_DIR" -name '*.go' -newer "$GO_BIN" -print -quit | grep -q .; then
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

build_ts() {
    # Bundle the TS kernel once (esbuild, cached by source mtimes) so each band
    # runs via plain `node` (~60ms) instead of npx tsx (~1.5s). With 455 bands
    # that is the difference between seconds and 11+ minutes of startup tax.
    local bundle="$TS_DIR/dist/main.mjs"
    local stale=0
    if [[ ! -f "$bundle" ]]; then stale=1; else
        local f
        for f in "$TS_DIR"/src/*.ts; do
            [[ "$f" -nt "$bundle" ]] && { stale=1; break; }
        done
    fi
    if [[ "$stale" == "1" ]]; then
        echo "  bundling ts kernel..." >&2
        npx --yes esbuild "$TS_DIR/src/main.ts" --bundle --platform=node             --format=esm --outfile="$bundle" --log-level=warning >&2 || rm -f "$bundle"
    fi
}

build_go &
build_rs &
build_ts &
wait

run_ts() {
    local bundle="$TS_DIR/dist/main.mjs"
    local loader="$PWD/$TS_DIR/node_modules/tsx/dist/loader.mjs"
    if [[ -f "$bundle" ]]; then
        node --stack_size="$HOST_STACK_KB" "$bundle" "$@"
    elif [[ -x "$TS_DIR/node_modules/.bin/tsx" ]]; then
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

# Source-compiled preludes are cached by CONTENT (file + compiler chain): the
# same unchanged core.fk compiles once, not once per band. Without this cache
# every validate invocation re-ran the full BML source-compiler (~12s) on
# identical input — 455 bands paid ~90 serial minutes for the same artifact.
SOURCE_CACHE_DIR="form-stdlib/.cache/source-compiled"
mkdir -p "$SOURCE_CACHE_DIR"
compiler_stamp=""
compiler_chain=("form-stdlib/form-ontology-loader.fk" "form-stdlib/line-grammar.fk" "form-stdlib/bmf-core.fk" "form-stdlib/bmf-grammar.fk" "form-stdlib/bml.fk" "form-stdlib/bml-source.fk" "form-stdlib/source-compiler.fk")
compiler_stamp="$(cat "${compiler_chain[@]}" "$GO_BIN" 2>/dev/null | shasum | cut -c1-16)"

prepared_args=()
prepare_sources() {
    prepared_args=()
    local src out safe driver key cached
    for src in "$@"; do
        if grep -Eq '^[[:space:]]*section \[' "$src"; then
            key="$(cat "$src" | shasum | cut -c1-16)-$compiler_stamp"
            cached="$SOURCE_CACHE_DIR/$key.fk"
            if [[ ! -s "$cached" ]]; then
                safe="${src//\//__}"
                out="$source_compile_dir/$safe"
                driver="$source_compile_dir/compile-${safe}.fk"
                printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$out" > "$driver"
                "$GO_BIN" "${compiler_chain[@]}" "$driver" >/dev/null
                if [[ -s "$out" ]]; then
                    mv -f "$out" "$cached" 2>/dev/null || cp "$out" "$cached"
                else
                    prepared_args+=("$src")
                    continue
                fi
            fi
            prepared_args+=("$cached")
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
    local go_out rs_out ts_out legs
    prepare_sources "$@"
    # The three kernels run CONCURRENTLY: a band's wall time is max(leg), not
    # sum — on compiler-heavy bands the Go+Rust legs ride inside the TS leg's
    # shadow for free. Outputs stay byte-compared exactly as before.
    legs="$(mktemp -d "${TMPDIR:-/tmp}/form-legs.XXXXXX")"
    ( "$GO_BIN" "${prepared_args[@]}" > "$legs/go" 2>&1 || true ) &
    ( "$RS_BIN" "${prepared_args[@]}" > "$legs/rs" 2>&1 || true ) &
    ( run_ts "${prepared_args[@]}" > "$legs/ts" 2>&1 || true ) &
    wait
    go_out=$(cat "$legs/go"); rs_out=$(cat "$legs/rs"); ts_out=$(cat "$legs/ts")
    rm -rf "$legs"
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

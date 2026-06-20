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
# Resolve a working Python 3: prefer `py -3` on Windows (a bare `python3` there
# resolves to the App-Execution-Alias stub that prints "Python was not found"),
# and verify the interpreter actually runs before using it.
BP_PY=""
if command -v py >/dev/null 2>&1 && py -3 --version >/dev/null 2>&1; then
    BP_PY="py -3"
elif command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    BP_PY="python3"
fi
if [[ -n "$BP_PY" && -f ../scripts/gen_bp_table.py ]]; then
    $BP_PY ../scripts/gen_bp_table.py >/dev/null 2>&1 || true
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

# The fourth sibling — the universal walker binary emitted from Form
# recipes — joins covered bands as a fourth leg. Built AFTER the Go kernel
# (its C source is emitted by running the Go walker); everything degrades
# honestly when clang or the manifest is absent. See scripts/fourth-arm.sh.
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh
build_fourth

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
compiler_stamp="$(cat "${compiler_chain[@]}" "$GO_BIN" 2>/dev/null | form_hash | cut -c1-16)"

prepared_args=()
prepare_sources() {
    prepared_args=()
    local src out safe driver key cached
    for src in "$@"; do
        if grep -Eq '^[[:space:]]*section \[' "$src"; then
            key="$(cat "$src" | form_hash | cut -c1-16)-$compiler_stamp"
            cached="$SOURCE_CACHE_DIR/$key.fk"
            if [[ ! -s "$cached" ]]; then
                safe="${src//\//__}"
                out="$(mktemp "$SOURCE_CACHE_DIR/.${key}.XXXXXX")"
                driver="$(mktemp "$source_compile_dir/compile-${safe}.XXXXXX")"
                printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$out" > "$driver"
                if "$GO_BIN" "${compiler_chain[@]}" "$driver" >/dev/null && [[ -s "$out" ]]; then
                    mv -f "$out" "$cached"
                else
                    rm -f "$out" "$driver"
                    if [[ ! -s "$cached" ]]; then
                        prepared_args+=("$src")
                        continue
                    fi
                fi
                rm -f "$out" "$driver"
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
    # Fourth leg: when the workload's band is in the fourth-arm manifest,
    # its pre-flattened table runs on the emitted universal walker (fkwu)
    # alongside the three walkers. Native execution answers in milliseconds,
    # so max(legs) — the band's wall time — does not move.
    local fourth_tbl="" fk_out=""
    if fourth_available; then
        fourth_tbl="$(fourth_table_for_band "${*: -1}")"
    fi
    # The three kernels run CONCURRENTLY: a band's wall time is max(leg), not
    # sum — on compiler-heavy bands the Go+Rust legs ride inside the TS leg's
    # shadow for free. Outputs stay byte-compared exactly as before.
    #
    # Each leg gets its OWN TMPDIR under the legs dir: bands reach scratch
    # space through the `temp_dir` native, so concurrent sibling legs (and
    # concurrent validate runs) never share a scratch path. The legs dir is
    # removed after comparison, so band scratch leaves no sediment.
    legs="$(mktemp -d "${TMPDIR:-/tmp}/form-legs.XXXXXX")"
    prepare_leg_args() {
        local leg="$1"
        local root="$legs/tmp-$leg"
        local outdir="$legs/src-$leg"
        local src out
        mkdir -p "$root" "$outdir"
        leg_args=()
        for src in "${prepared_args[@]}"; do
            if grep -q '"/tmp/' "$src"; then
                out="$outdir/$(basename "$src")"
                sed "s#\"/tmp/#\"$root/#g" "$src" > "$out"
                leg_args+=("$out")
            else
                leg_args+=("$src")
            fi
        done
    }
    prepare_leg_args go
    go_args=("${leg_args[@]}")
    prepare_leg_args rs
    rs_args=("${leg_args[@]}")
    prepare_leg_args ts
    ts_args=("${leg_args[@]}")
    ( TMPDIR="$legs/tmp-go" "$GO_BIN" "${go_args[@]}" > "$legs/go" 2>&1 || true ) &
    ( TMPDIR="$legs/tmp-rs" "$RS_BIN" "${rs_args[@]}" > "$legs/rs" 2>&1 || true ) &
    ( TMPDIR="$legs/tmp-ts" run_ts "${ts_args[@]}" > "$legs/ts" 2>&1 || true ) &
    if [[ -n "$fourth_tbl" ]]; then
        ( TMPDIR="$legs/tmp-fk" "$FKWU" "$fourth_tbl" 0 2>/dev/null | head -1 > "$legs/fk" || true ) &
    fi
    wait
    go_out=$(cat "$legs/go"); rs_out=$(cat "$legs/rs"); ts_out=$(cat "$legs/ts")
    if [[ -n "$fourth_tbl" ]]; then fk_out=$(cat "$legs/fk" 2>/dev/null || true); fi
    rm -rf "$legs" 2>/dev/null || true
    if [[ "$go_out" == "$rs_out" && "$go_out" == "$ts_out" ]] \
        && { [[ -z "$fourth_tbl" ]] || [[ "$fk_out" == "$go_out" ]]; }; then
        printf "  ✓  %-30s  → %s\n" "$label" "$go_out"
        ok=$((ok + 1))
        if [[ -n "$fourth_tbl" ]]; then fourth_ok=$((fourth_ok + 1)); fi
        if [[ -n "${SUITE_STATUS_FILE:-}" ]]; then
            if [[ -n "$fourth_tbl" ]]; then echo "ok fourth" > "$SUITE_STATUS_FILE"; else echo "ok" > "$SUITE_STATUS_FILE"; fi
        fi
    elif [[ -n "$fourth_tbl" ]]; then
        printf "  ✗  %-30s\n      go         = %s\n      rust       = %s\n      typescript = %s\n      fourth     = %s\n" \
            "$label" "$go_out" "$rs_out" "$ts_out" "$fk_out"
        fail=$((fail + 1))
        if [[ -n "${SUITE_STATUS_FILE:-}" ]]; then echo "fail" > "$SUITE_STATUS_FILE"; fi
    else
        printf "  ✗  %-30s\n      go         = %s\n      rust       = %s\n      typescript = %s\n" \
            "$label" "$go_out" "$rs_out" "$ts_out"
        fail=$((fail + 1))
        if [[ -n "${SUITE_STATUS_FILE:-}" ]]; then echo "fail" > "$SUITE_STATUS_FILE"; fi
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
        if [[ -n "${SUITE_STATUS_FILE:-}" ]]; then echo "ok" > "$SUITE_STATUS_FILE"; fi
    else
        printf "  ✗  %-30s\n      go         = %s\n      rust       = %s\n      typescript = %s\n" \
            "$label" "$go_out" "$rs_out" "$ts_out"
        fail=$((fail + 1))
        if [[ -n "${SUITE_STATUS_FILE:-}" ]]; then echo "fail" > "$SUITE_STATUS_FILE"; fi
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
fourth_ok=0

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
    # Pre-flatten every covered band's table in one Go run before the
    # suite fans out — cold cache pays ~20s once; warm runs skip it.
    fourth_prepare_all
    # Pre-compile the one prelude every band shares so the pool's first
    # wave doesn't race N copies of the same compile (atomic mv converges
    # them, but each lost race re-pays the full source-compiler walk).
    prepare_sources form-stdlib/core.fk

    # The suite fans out ACROSS bands: each workload is one job in a pool
    # (VALIDATE_JOBS wide, default 8), writing an ordered result block plus
    # a status file; the aggregation prints blocks in collection order and
    # counts from the status files. A band's legs were already concurrent;
    # this makes the bands themselves concurrent — the suite's wall time is
    # sum(bands)/jobs instead of sum(bands). Caches stay safe under the
    # fan-out: source-compile and fourth-table writes are content-keyed and
    # atomic (mv), every leg owns a private TMPDIR.
    SUITE_PAR="${VALIDATE_JOBS:-8}"
    suite_dir="$(mktemp -d "${TMPDIR:-/tmp}/form-suite.XXXXXX")"
    wl_labels=()
    wl_args=()
    add_workload() {
        local label="$1"; shift
        wl_labels+=("$label")
        local joined="" a
        for a in "$@"; do joined="$joined$a"$'\x1f'; done
        wl_args+=("$joined")
    }
    # --- form-samples/*.fk: self-contained files ------------------------
    for f in form-samples/*.fk; do
        add_workload "$(basename "$f")" "$f"
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
                add_workload "stdlib/$(basename "$f")" "form-stdlib/core.fk" $preludes "$f"
            elif [[ -f "$module" && "$module" != "$f" ]]; then
                add_workload "stdlib/$(basename "$f")" "form-stdlib/core.fk" "$module" "$f"
            else
                add_workload "stdlib/$(basename "$f")" "form-stdlib/core.fk" "$f"
            fi
        done
    fi
    run_one_indexed() {
        local idx="$1"
        local IFS=$'\x1f'
        # shellcheck disable=SC2206
        local files=(${wl_args[$idx]})
        SUITE_STATUS_FILE="$suite_dir/$idx.status" \
            run_workload "${wl_labels[$idx]}" "${files[@]}" > "$suite_dir/$idx.out" 2>&1 || true
    }
    i=0
    total=${#wl_labels[@]}
    while [[ $i -lt $total ]]; do
        run_one_indexed "$i" &
        i=$((i + 1))
        while [[ "$(jobs -r | wc -l)" -ge "$SUITE_PAR" ]]; do sleep 0.2; done
    done
    wait
    i=0
    while [[ $i -lt $total ]]; do
        cat "$suite_dir/$i.out" 2>/dev/null || true
        case "$(cat "$suite_dir/$i.status" 2>/dev/null || echo fail)" in
            "ok fourth") ok=$((ok + 1)); fourth_ok=$((fourth_ok + 1)) ;;
            ok)          ok=$((ok + 1)) ;;
            *)           fail=$((fail + 1)) ;;
        esac
        i=$((i + 1))
    done
    rm -rf "$suite_dir"
fi

echo ""
if [[ $fourth_ok -gt 0 ]]; then
    echo "  fourth arm: $fourth_ok band(s) four-way (fkwu + pre-flattened tables)"
fi
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

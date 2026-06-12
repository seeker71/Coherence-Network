#!/usr/bin/env bash
# fourth-arm-survey.sh — sense how far the fourth kernel's band coverage
# reaches TODAY: every form-stdlib/tests/*-band.fk outside the manifest is
# classified (BML-dialect / multi-prelude / shape) and, where the flattener
# can read it, flattened + run on fkwu against the Go walker's own verdict.
# Output: one line per band in $OUT/results.tsv —
#   stem<TAB>category<TAB>expected<TAB>fkw
# Categories: pass mismatch bml multi-prelude multi-line non-1line-int
#             flatten-empty go-timeout in-manifest
set -u
cd "$(dirname "$0")/.."

GO_BIN="form-kernel-go/bin-go"
OUT="form-stdlib/.cache/fourth-survey"
mkdir -p "$OUT"
source scripts/fourth-arm.sh
if [[ "${1:-}" != "--one" ]]; then
    build_fourth
else
    # workers reuse the standing binary; no rebuild race
    FKWU="$(find "$FOURTH_DIR" -maxdepth 1 -name 'fkwu-*' -perm +111 | head -1)"
fi
fourth_available || { echo "no fkwu — abort"; exit 1; }

EMPTY="$OUT/empty.fk"
: > "$EMPTY"

# portable timeout (macOS has no coreutils timeout; perl alarm carries it)
run_to() { local secs="$1"; shift; perl -e 'alarm shift; exec @ARGV' "$secs" "$@"; }

# BML-dialect sources (core.fk included) must ride the source-compiler before
# a kernel walks them — validate.sh's prepare_sources discipline, same cache.
SC_DIR="form-stdlib/.cache/source-compiled"
mkdir -p "$SC_DIR"
compiler_chain=(form-stdlib/form-ontology-loader.fk form-stdlib/line-grammar.fk \
    form-stdlib/bmf-core.fk form-stdlib/bmf-grammar.fk form-stdlib/bml.fk \
    form-stdlib/bml-source.fk form-stdlib/source-compiler.fk)
compiler_stamp="$(cat "${compiler_chain[@]}" "$GO_BIN" 2>/dev/null | shasum | cut -c1-16)"
prep() { # file -> compiled artifact path (passthrough for plain Form)
    local src="$1" key cached d
    if ! grep -Eq '^[[:space:]]*section \[' "$src"; then printf '%s\n' "$src"; return; fi
    key="$(shasum < "$src" | cut -c1-16)-$compiler_stamp"
    cached="$SC_DIR/$key.fk"
    if [[ ! -s "$cached" ]]; then
        d="$(mktemp -d "${TMPDIR:-/tmp}/fk-prep.XXXXXX")"
        printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$d/out.fk" > "$d/c.fk"
        run_to 180 "$GO_BIN" "${compiler_chain[@]}" "$d/c.fk" >/dev/null 2>&1 || true
        [[ -s "$d/out.fk" ]] && mv -f "$d/out.fk" "$cached"
        rm -rf "$d"
    fi
    if [[ -s "$cached" ]]; then printf '%s\n' "$cached"; else printf '%s\n' "$src"; fi
}

survey_one() {
    local band="$1" stem pres noncores cls="single" exp d tbl fkw f srcs=() rl pl
    stem="$(basename "$band")"; stem="${stem%-band.fk}"
    # in-manifest rows are already gated; skip
    if awk -v b="$stem" '$1==b{found=1} END{exit !found}' fourth-arm-bands.txt 2>/dev/null; then
        printf '%s\tin-manifest\t-\t-\n' "$stem"; return
    fi
    pres="$(grep -E '^; preludes:' "$band" 2>/dev/null | head -1 | sed 's/^; preludes://')"
    noncores="$(printf '%s\n' $pres | grep -v 'core\.fk' | grep . || true)"
    if grep -Eq '^[[:space:]]*section \[' "$band" $noncores 2>/dev/null; then
        cls="bml"
    elif [[ "$(printf '%s\n' "$noncores" | grep -c .)" -gt 1 ]]; then
        cls="multi"
    fi
    # io bands stay unexecuted: they reach the host filesystem/processes (a
    # cache-eviction band once removed form-stdlib/.cache out from under a
    # running survey), and the io family is a named wall — no table to gain
    if grep -hEq '\((write_file|write_form_binary|read_form_binary|file_mtime|file_size|temp_dir|scan_run|source_scan_file|shell_run|tcp_|http_)' "$band" $noncores 2>/dev/null; then
        printf '%s\t%s-io\t-\t-\n' "$stem" "$cls"; return
    fi
    # the band's source list (non-core preludes then the band), each riding
    # the source-compiler when BML-dialect — same discipline as validate.sh
    if [[ -z "$noncores" && -f "form-stdlib/$stem.fk" ]]; then
        noncores="form-stdlib/$stem.fk"
    fi
    for f in $noncores "$band"; do
        srcs+=("$(prep "$f")")
    done
    # the Go walker's own verdict (the siblings' shape; full output)
    exp="$(run_to 90 "$GO_BIN" "$(prep form-stdlib/core.fk)" "${srcs[@]}" 2>/dev/null || true)"
    if [[ -z "$exp" ]]; then
        printf '%s\t%s-go-timeout\t-\t-\n' "$stem" "$cls"; return
    fi
    if [[ "$(printf '%s\n' "$exp" | wc -l)" -gt 1 ]]; then
        printf '%s\t%s-multi-line\t%s\t-\n' "$stem" "$cls" "$(printf '%s' "$exp" | head -1)"; return
    fi
    if ! [[ "$exp" =~ ^-?[0-9]+$ ]]; then
        printf '%s\t%s-non-1line-int\t%s\t-\n' "$stem" "$cls" "$exp"; return
    fi
    # flatten every source through the multi-source string-pool door (the
    # shim rides first: core vocabulary + string stones as function rows)
    rl=" (read_file \"form-stdlib/fourth-shim.fk\")"
    for f in "${srcs[@]}"; do rl="$rl (read_file \"$f\")"; done
    d="$(mktemp -d "${TMPDIR:-/tmp}/fk-survey.XXXXXX")"
    cat form-stdlib/minimal-surface.fk form-stdlib/fourth-walker.fk \
        form-stdlib/fourth-walker-emit.fk form-stdlib/form-parse.fk \
        form-stdlib/form-flatten.fk > "$d/driver.fk"
    printf '(print (fks-table-file (flt-srcs-fns (list%s)) (flt-srcs-pool (list%s) (list))))\n' \
        "$rl" "$rl" >> "$d/driver.fk"
    tbl="$OUT/t-$stem.txt"
    run_to 120 "$GO_BIN" "$d/driver.fk" 2>/dev/null > "$tbl" || true
    rm -rf "$d"
    if [[ ! -s "$tbl" ]]; then
        printf '%s\t%s-flatten-empty\t%s\t-\n' "$stem" "$cls" "$exp"; return
    fi
    fkw="$(run_to 60 "$FKWU" "$tbl" 0 2>/dev/null | head -1 || true)"
    if [[ "$fkw" == "$exp" ]]; then
        printf '%s\t%s-pass\t%s\t%s\n' "$stem" "$cls" "$exp" "$fkw"
    else
        printf '%s\t%s-mismatch\t%s\t%s\n' "$stem" "$cls" "$exp" "${fkw:-∅}"
    fi
}

if [[ "${1:-}" == "--one" ]]; then
    survey_one "$2" > "$OUT/r-$(basename "${2%-band.fk}").tsv"
    exit 0
fi

rm -f "$OUT"/r-*.tsv
ls form-stdlib/tests/*-band.fk | xargs -P 8 -I{} bash "scripts/fourth-arm-survey.sh" --one {}
cat "$OUT"/r-*.tsv > "$OUT/results.tsv"

echo "── survey ──"
cut -f2 "$OUT/results.tsv" | sort | uniq -c | sort -rn
echo "results: $OUT/results.tsv"

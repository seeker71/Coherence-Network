#!/usr/bin/env bash
# fourth-arm.sh — the emitted fourth kernel as a validate.sh leg.
#
# Sourced by validate.sh (cwd = form/). The fourth sibling is the universal
# walker binary (fkwu) whose C source is emitted entirely by Form recipes
# (fourth-walker-emit.fk, fkc-emit-universal). Bands listed in
# fourth-arm-bands.txt — each one already gated four-way by
# scripts/hati_os_kernel_audit.sh — run on it as a fourth leg: the band's
# UNMODIFIED source is flattened once into a node-table file (the
# pre-compiled artifact), cached by content, and the binary answers in
# milliseconds. A band's wall time stays max(legs); the fourth witness is
# effectively free.
#
# Everything degrades honestly: no clang, no manifest, or an emission
# failure simply leaves FKWU/table empty and the band runs three-kernel only as
# before — the suite never goes red because the fourth arm could not build,
# only when it DISAGREES.

FOURTH_DIR="form-stdlib/.cache/fourth"
FOURTH_MANIFEST="fourth-arm-bands.txt"
# The emitter chain: every file whose content shapes either the fkwu binary
# or a flattened table. Cache keys hash these so a flattener or walker
# change rebuilds exactly what it touches.
FOURTH_CHAIN=(
    form-stdlib/minimal-surface.fk
    form-stdlib/hati-os-kernel.fk
    form-stdlib/hati-os-kernel-emit.fk
    form-stdlib/form-parse.fk
    form-stdlib/form-flatten.fk
    form-stdlib/fourth-shim.fk
)
# the shim rides every flatten as the FIRST source: core vocabulary and the
# string stones resolve as ordinary function rows; band defns shadow it
FOURTH_SHIM="form-stdlib/fourth-shim.fk"
FKWU=""

fourth_available() { [[ -n "$FKWU" && -x "$FKWU" ]]; }

# build_fourth — the standing fkwu binary, cached by emitter content.
build_fourth() {
    [[ -f "$FOURTH_MANIFEST" ]] || return 0
    command -v clang >/dev/null 2>&1 || return 0
    mkdir -p "$FOURTH_DIR"
    local stamp out tmp d
    stamp="$(cat "${FOURTH_CHAIN[@]}" "$GO_BIN" 2>/dev/null | shasum | cut -c1-16)"
    out="$FOURTH_DIR/fkwu-$stamp"
    if [[ ! -x "$out" ]]; then
        echo "  building fourth kernel (fkwu)..." >&2
        d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth.XXXXXX")"
        cat form-stdlib/minimal-surface.fk form-stdlib/hati-os-kernel.fk \
            form-stdlib/hati-os-kernel-emit.fk > "$d/uni-driver.fk"
        printf '(print "==UNI==")\n(print (fkc-emit-universal))\n(print "==END==")\n' >> "$d/uni-driver.fk"
        "$GO_BIN" "$d/uni-driver.fk" 2>/dev/null > "$d/uni.out" || true
        sed -n '/^==UNI==$/,/^==END==$/p' "$d/uni.out" | sed -e '1d' -e '$d' > "$d/uni.c"
        tmp="$(mktemp "$FOURTH_DIR/.fkwu-$stamp.XXXXXX")"
        if [[ -s "$d/uni.c" ]] && clang -O2 -o "$tmp" "$d/uni.c" 2>/dev/null; then
            mv -f "$tmp" "$out"
        else
            rm -f "$tmp"
            echo "  fourth kernel build did not land — bands run three-kernel only" >&2
        fi
        rm -rf "$d"
    fi
    [[ -x "$out" ]] && FKWU="$out"
    # Compost stale binaries from earlier emitter generations.
    find "$FOURTH_DIR" -maxdepth 1 -name 'fkwu-*' ! -name "$(basename "$out")" -delete 2>/dev/null || true
}

# fourth_band_stem — manifest stem for a band file path, or empty. The fourth
# arm only applies to a CANONICAL band — the workload's last file living under
# form-stdlib/tests/. A same-named sample elsewhere (e.g. a cross-modal demo
# whose basename collides with a manifest stem) never resolves, because its
# table would still be built from form-stdlib/tests/<stem>-band.fk and compared
# against the sample's own three-kernel output — a false divergence. Anchoring
# to the tests/ path keeps the stem the contract for the real band only.
fourth_band_stem() {
    local band="$1" stem
    [[ "$band" == form-stdlib/tests/* || "$band" == */form-stdlib/tests/* ]] || return 0
    stem="$(basename "$band")"
    stem="${stem%.fk}"
    stem="${stem%-band}"
    [[ -f "$FOURTH_MANIFEST" ]] || return 0
    awk -v b="$stem" '$1==b{print $1; exit}' "$FOURTH_MANIFEST"
}

# fourth_band_srcs — the band's source list: every non-core prelude in
# declared order, then the band file itself (same-name convention as the
# fallback when no prelude is declared).
fourth_band_srcs() {
    local stem="$1" band="form-stdlib/tests/$stem-band.fk" mods
    # A manifest stem maps to tests/<stem>-band.fk OR the plain tests/<stem>.fk —
    # fourth_band_stem strips -band when reading, so both are the same band.
    # Read the preludes header from whichever file exists, else a stem registered
    # under the plain name silently builds an empty table and runs three-kernel only.
    [[ -f "$band" ]] || band="form-stdlib/tests/$stem.fk"
    # Drop ONLY the exact core.fk prelude (the shim mirrors it). Anchor the match
    # to a path boundary so sibling-named modules — substrate-core.fk, bmf-core.fk
    # — keep their place in the source list instead of vanishing as substrings.
    mods="$(grep -E '^; preludes:' "$band" 2>/dev/null | head -1 | sed 's/^; preludes://' \
        | tr ' ' '\n' | grep -vE '(^|/)core\.fk$' | grep . || true)"
    [[ -z "$mods" && -f "form-stdlib/$stem.fk" ]] && mods="form-stdlib/$stem.fk"
    printf '%s\n' $mods "$band"
}

# fourth_prep_srcs — prepared source paths for a stem, one per line: a
# BML-dialect file rides validate.sh's prepare_sources (when in scope) so
# the flattener always reads plain Form; empty when a source is missing.
fourth_prep_srcs() {
    local stem="$1" f
    while IFS= read -r f; do
        [[ -f "$f" ]] || return 0
        if grep -Eq '^[[:space:]]*section \[' "$f" && declare -f prepare_sources >/dev/null; then
            prepare_sources "$f"
            printf '%s\n' "${prepared_args[0]}"
        else
            printf '%s\n' "$f"
        fi
    done < <(fourth_band_srcs "$stem")
}

# fourth_flatten_expr — the driver line that flattens a source list through
# the multi-source door (fks carries the string pool; fkc is pool-free).
fourth_flatten_expr() {
    local kind="$1"; shift
    local srcs=("$@") count last band mods=" (read_file \"$FOURTH_SHIM\")" band_read f i
    count="${#srcs[@]}"
    [[ "$count" -gt 0 ]] || return 1
    last=$((count - 1))
    band="${srcs[$last]}"
    for ((i = 0; i < last; i++)); do
        f="${srcs[$i]}"
        mods="$mods (read_file \"$f\")"
    done
    band_read="(read_file \"$band\")"
    if [[ "$kind" == "fks" ]]; then
        printf '(print (fks-table-file (flt-band-sources-fns (list%s) %s) (flt-band-sources-pool (list%s) %s)))\n' "$mods" "$band_read" "$mods" "$band_read"
    else
        printf '(print (fkc-table-file (flt-band-sources-fns (list%s) %s)))\n' "$mods" "$band_read"
    fi
}

# fourth_table — cached flattened node-table for one band (path on stdout).
# Emits through the Go walker on a cache miss; empty output means the band
# runs three-kernel only this time.
fourth_table() {
    local stem="$1" kind key out d f srcs=()
    kind="$(awk -v b="$stem" '$1==b{print $2; exit}' "$FOURTH_MANIFEST")"
    [[ -n "$kind" ]] || return 0
    while IFS= read -r f; do srcs+=("$f"); done < <(fourth_prep_srcs "$stem")
    [[ "${#srcs[@]}" -ge 1 ]] || return 0
    key="$(cat "${srcs[@]}" "${FOURTH_CHAIN[@]}" 2>/dev/null | shasum | cut -c1-16)"
    out="$FOURTH_DIR/t-$stem-$key.txt"
    if [[ ! -s "$out" ]]; then
        d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth-t.XXXXXX")"
        cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
        fourth_flatten_expr "$kind" "${srcs[@]}" >> "$d/driver.fk"
        "$GO_BIN" "$d/driver.fk" 2>/dev/null > "$out.tmp" && mv -f "$out.tmp" "$out" || rm -f "$out.tmp"
        rm -rf "$d"
    fi
    [[ -s "$out" ]] && printf '%s\n' "$out"
}

# fourth_table_for_band — the cached table for a band FILE PATH (the last
# workload argument), or empty when the band is outside the manifest.
fourth_table_for_band() {
    local stem
    stem="$(fourth_band_stem "$1")"
    [[ -n "$stem" ]] || return 0
    fourth_table "$stem"
}

# fourth_run_chunk — flatten ONE chunk's driver through the Go walker in a
# single pass, then split the marker-delimited output into per-band tables.
#   driver: FOURTH_CHAIN  +  (==T-stem== marker, flatten expr)*  +  ==T-END==
#   plan:   one "stem<TAB>outpath" line per band, in driver order
# Self-contained (reads only its two files), so it runs safely as a background
# job: every table publishes atomically (mv -f "$cur.tmp" "$cur"), so parallel
# chunks never collide. A band whose flatten emits nothing leaves no table and
# runs three-kernel only — honest degradation, never a red suite.
fourth_run_chunk() {
    local driver="$1" plan="$2" out_all="$1.out"
    "$GO_BIN" "$driver" 2>/dev/null > "$out_all" || true
    local stems=() outs=() s o
    while IFS=$'\t' read -r s o; do stems+=("$s"); outs+=("$o"); done < "$plan"
    local n="${#stems[@]}" p cur nextmark
    for ((p = 0; p < n; p++)); do
        cur="${outs[$p]}"
        if ((p + 1 < n)); then nextmark="==T-${stems[$((p + 1))]}=="; else nextmark="==T-END=="; fi
        sed -n "/^==T-${stems[$p]}==\$/,/^${nextmark}\$/p" "$out_all" | sed -e '1d' -e '$d' > "$cur.tmp"
        if [[ -s "$cur.tmp" ]]; then mv -f "$cur.tmp" "$cur"; else rm -f "$cur.tmp"; fi
    done
    rm -f "$out_all"
}

# fourth_prepare_all — emit every MISSING manifest table before the suite fans
# out. Each Go walker run re-parses the whole FOURTH_CHAIN, so the cost that
# matters is the NUMBER of walker runs, not the band count. We group the missing
# bands into CHUNKS of $batch_max and flatten each chunk in ONE walker run
# (chain parsed once per chunk) — turning N separate runs (one per band on a
# cold cache) into ceil(N/batch_max). Chunks fan out across cores in waves of
# $jobs with a plain `wait` barrier: no busy-poll, no `wait -n`, holds in bash
# 3.2 (macOS default). Warm runs (missing=0) return before any walker starts.
fourth_prepare_all() {
    fourth_available || return 0
    [[ -f "$FOURTH_MANIFEST" ]] || return 0
    local workdir stem kind key out missing=0 f srcs driver plan cidx=0 ccount=0
    local batch_max="${FOURTH_PREPARE_ALL_BATCH_MAX:-48}"
    workdir="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth-all.XXXXXX")"
    while read -r stem kind _; do
        [[ -z "$stem" || "$stem" == \#* ]] && continue
        srcs=()
        while IFS= read -r f; do srcs+=("$f"); done < <(fourth_prep_srcs "$stem")
        [[ "${#srcs[@]}" -ge 1 ]] || continue
        key="$(cat "${srcs[@]}" "${FOURTH_CHAIN[@]}" 2>/dev/null | shasum | cut -c1-16)"
        out="$FOURTH_DIR/t-$stem-$key.txt"
        [[ -s "$out" ]] && continue
        missing=$((missing + 1))
        if [[ "$ccount" -eq 0 ]]; then        # open a fresh chunk driver + plan
            driver="$workdir/driver-$cidx.fk"; plan="$workdir/plan-$cidx.tsv"
            cat "${FOURTH_CHAIN[@]}" > "$driver"; : > "$plan"
        fi
        printf '(print "==T-%s==")\n' "$stem" >> "$driver"
        fourth_flatten_expr "$kind" "${srcs[@]}" >> "$driver"
        printf '%s\t%s\n' "$stem" "$out" >> "$plan"
        ccount=$((ccount + 1))
        if [[ "$ccount" -ge "$batch_max" ]]; then   # seal a full chunk
            printf '(print "==T-END==")\n' >> "$driver"
            cidx=$((cidx + 1)); ccount=0
        fi
    done < "$FOURTH_MANIFEST"
    if [[ "$ccount" -gt 0 ]]; then               # seal the trailing partial chunk
        printf '(print "==T-END==")\n' >> "$driver"
        cidx=$((cidx + 1))
    fi
    if [[ "$missing" -eq 0 ]]; then
        rm -rf "$workdir"
        return 0
    fi
    local jobs="${FOURTH_PREPARE_ALL_JOBS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)}"
    [[ "$jobs" =~ ^[0-9]+$ && "$jobs" -ge 1 ]] || jobs=4
    echo "  flattening $missing band tables for the fourth arm in $cidx walker run(s) across $jobs cores (cold cache; chunk $batch_max)..." >&2
    local k inflight=0
    for ((k = 0; k < cidx; k++)); do
        fourth_run_chunk "$workdir/driver-$k.fk" "$workdir/plan-$k.tsv" &
        inflight=$((inflight + 1))
        if [[ "$inflight" -ge "$jobs" ]]; then wait || true; inflight=0; fi
    done
    wait || true
    rm -rf "$workdir"
    # Compost stale tables from earlier source generations.
    find "$FOURTH_DIR" -maxdepth 1 -name 't-*' -mtime +14 -delete 2>/dev/null || true
}

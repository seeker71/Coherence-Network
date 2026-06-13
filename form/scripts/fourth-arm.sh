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

# fourth_band_stem — manifest stem for a band file path, or empty.
fourth_band_stem() {
    local band="$1" stem
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
    mods="$(grep -E '^; preludes:' "$band" 2>/dev/null | head -1 | sed 's/^; preludes://' \
        | tr ' ' '\n' | grep -v 'core\.fk' | grep . || true)"
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

# fourth_prepare_all — batch-emit every missing manifest table in ONE Go
# walker run (the flattener chain parses once, not once per band). Called
# before the full suite; single-band runs fall back to fourth_table's
# per-band miss path.
fourth_prepare_all() {
    fourth_available || return 0
    [[ -f "$FOURTH_MANIFEST" ]] || return 0
    local d stems=() outs=() stem kind key out missing=0 f srcs
    d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth-all.XXXXXX")"
    cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
    while read -r stem kind _; do
        [[ -z "$stem" || "$stem" == \#* ]] && continue
        srcs=()
        while IFS= read -r f; do srcs+=("$f"); done < <(fourth_prep_srcs "$stem")
        [[ "${#srcs[@]}" -ge 1 ]] || continue
        key="$(cat "${srcs[@]}" "${FOURTH_CHAIN[@]}" 2>/dev/null | shasum | cut -c1-16)"
        out="$FOURTH_DIR/t-$stem-$key.txt"
        [[ -s "$out" ]] && continue
        missing=$((missing + 1))
        stems+=("$stem")
        outs+=("$out")
        printf '(print "==T-%s==")\n' "$stem" >> "$d/driver.fk"
        fourth_flatten_expr "$kind" "${srcs[@]}" >> "$d/driver.fk"
    done < "$FOURTH_MANIFEST"
    if [[ "$missing" -eq 0 ]]; then
        rm -rf "$d"
        return 0
    fi
    echo "  flattening $missing band tables for the fourth arm..." >&2
    printf '(print "==T-END==")\n' >> "$d/driver.fk"
    "$GO_BIN" "$d/driver.fk" 2>/dev/null > "$d/all.out" || true
    local i cur=""
    for ((i = 0; i < ${#stems[@]}; i++)); do
        cur="${outs[$i]}"
        if ((i + 1 < ${#stems[@]})); then
            sed -n "/^==T-${stems[$i]}==\$/,/^==T-${stems[$((i + 1))]}==\$/p" "$d/all.out" | sed -e '1d' -e '$d' > "$cur.tmp"
        else
            sed -n "/^==T-${stems[$i]}==\$/,/^==T-END==\$/p" "$d/all.out" | sed -e '1d' -e '$d' > "$cur.tmp"
        fi
        if [[ -s "$cur.tmp" ]]; then mv -f "$cur.tmp" "$cur"; else rm -f "$cur.tmp"; fi
    done
    rm -rf "$d"
    # Compost stale tables from earlier source generations.
    find "$FOURTH_DIR" -maxdepth 1 -name 't-*' -mtime +14 -delete 2>/dev/null || true
}

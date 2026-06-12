#!/usr/bin/env bash
# fourth-arm.sh — the emitted fourth kernel as a validate.sh leg.
#
# Sourced by validate.sh (cwd = form/). The fourth sibling is the universal
# walker binary (fkwu) whose C source is emitted entirely by Form recipes
# (fourth-walker-emit.fk, fkc-emit-universal). Bands listed in
# fourth-arm-bands.txt — each one already gated four-way by
# scripts/fourth_kernel_audit.sh — run on it as a fourth leg: the band's
# UNMODIFIED source is flattened once into a node-table file (the
# pre-compiled artifact), cached by content, and the binary answers in
# milliseconds. A band's wall time stays max(legs); the fourth witness is
# effectively free.
#
# Everything degrades honestly: no clang, no manifest, or an emission
# failure simply leaves FKWU/table empty and the band runs three-way as
# before — the suite never goes red because the fourth arm could not build,
# only when it DISAGREES.

FOURTH_DIR="form-stdlib/.cache/fourth"
FOURTH_MANIFEST="fourth-arm-bands.txt"
# The emitter chain: every file whose content shapes either the fkwu binary
# or a flattened table. Cache keys hash these so a flattener or walker
# change rebuilds exactly what it touches.
FOURTH_CHAIN=(
    form-stdlib/minimal-surface.fk
    form-stdlib/fourth-walker.fk
    form-stdlib/fourth-walker-emit.fk
    form-stdlib/form-parse.fk
    form-stdlib/form-flatten.fk
)
FKWU=""

fourth_available() { [[ -n "$FKWU" && -x "$FKWU" ]]; }

# build_fourth — the standing fkwu binary, cached by emitter content.
build_fourth() {
    [[ -f "$FOURTH_MANIFEST" ]] || return 0
    command -v clang >/dev/null 2>&1 || return 0
    mkdir -p "$FOURTH_DIR"
    local stamp out d
    stamp="$(cat "${FOURTH_CHAIN[@]}" "$GO_BIN" 2>/dev/null | shasum | cut -c1-16)"
    out="$FOURTH_DIR/fkwu-$stamp"
    if [[ ! -x "$out" ]]; then
        echo "  building fourth kernel (fkwu)..." >&2
        d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth.XXXXXX")"
        cat form-stdlib/minimal-surface.fk form-stdlib/fourth-walker.fk \
            form-stdlib/fourth-walker-emit.fk > "$d/uni-driver.fk"
        printf '(print "==UNI==")\n(print (fkc-emit-universal))\n(print "==END==")\n' >> "$d/uni-driver.fk"
        "$GO_BIN" "$d/uni-driver.fk" 2>/dev/null > "$d/uni.out" || true
        sed -n '/^==UNI==$/,/^==END==$/p' "$d/uni.out" | sed -e '1d' -e '$d' > "$d/uni.c"
        if [[ -s "$d/uni.c" ]] && clang -O2 -o "$out.tmp" "$d/uni.c" 2>/dev/null; then
            mv -f "$out.tmp" "$out"
        else
            rm -f "$out.tmp"
            echo "  fourth kernel build did not land — bands run three-way" >&2
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

# fourth_band_module — the band's module source: first non-core prelude,
# falling back to the same-name convention.
fourth_band_module() {
    local stem="$1" band="form-stdlib/tests/$stem-band.fk" mod
    mod="$(grep -E '^; preludes:' "$band" 2>/dev/null | head -1 | sed 's/^; preludes://' \
        | tr ' ' '\n' | grep -v 'core\.fk' | grep . | head -1)"
    [[ -z "$mod" ]] && mod="form-stdlib/$stem.fk"
    printf '%s\n' "$mod"
}

# fourth_table — cached flattened node-table for one band (path on stdout).
# Emits through the Go walker on a cache miss; empty output means the band
# runs three-way this time.
fourth_table() {
    local stem="$1" kind mod band key out d
    kind="$(awk -v b="$stem" '$1==b{print $2; exit}' "$FOURTH_MANIFEST")"
    [[ -n "$kind" ]] || return 0
    band="form-stdlib/tests/$stem-band.fk"
    mod="$(fourth_band_module "$stem")"
    [[ -f "$band" && -f "$mod" ]] || return 0
    key="$(cat "$mod" "$band" "${FOURTH_CHAIN[@]}" 2>/dev/null | shasum | cut -c1-16)"
    out="$FOURTH_DIR/t-$stem-$key.txt"
    if [[ ! -s "$out" ]]; then
        d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth-t.XXXXXX")"
        cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
        if [[ "$kind" == "fks" ]]; then
            printf '(print (fks-table-file (flt-band-fns (read_file "%s") (read_file "%s")) (flt-band-pool (read_file "%s") (read_file "%s"))))\n' \
                "$mod" "$band" "$mod" "$band" >> "$d/driver.fk"
        else
            printf '(print (fkc-table-file (flt-band-fns (read_file "%s") (read_file "%s"))))\n' \
                "$mod" "$band" >> "$d/driver.fk"
        fi
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
    local d stems=() outs=() stem kind mod band key out missing=0
    d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth-all.XXXXXX")"
    cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
    while read -r stem kind _; do
        [[ -z "$stem" || "$stem" == \#* ]] && continue
        band="form-stdlib/tests/$stem-band.fk"
        mod="$(fourth_band_module "$stem")"
        [[ -f "$band" && -f "$mod" ]] || continue
        key="$(cat "$mod" "$band" "${FOURTH_CHAIN[@]}" 2>/dev/null | shasum | cut -c1-16)"
        out="$FOURTH_DIR/t-$stem-$key.txt"
        [[ -s "$out" ]] && continue
        missing=$((missing + 1))
        stems+=("$stem")
        outs+=("$out")
        printf '(print "==T-%s==")\n' "$stem" >> "$d/driver.fk"
        if [[ "$kind" == "fks" ]]; then
            printf '(print (fks-table-file (flt-band-fns (read_file "%s") (read_file "%s")) (flt-band-pool (read_file "%s") (read_file "%s"))))\n' \
                "$mod" "$band" "$mod" "$band" >> "$d/driver.fk"
        else
            printf '(print (fkc-table-file (flt-band-fns (read_file "%s") (read_file "%s"))))\n' \
                "$mod" "$band" >> "$d/driver.fk"
        fi
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

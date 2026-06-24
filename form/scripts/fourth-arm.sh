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

# T_flat — the flattener (form-flatten.fk) flattened once over FOURTH_CHAIN into a
# committed bootstrap table. fkwu walks it to flatten every band, so bin-go leaves
# the per-band flatten path. The driver (fourth-flatten-driver.fk) reads a batch
# request on stdin and prints marker-framed tables — the same ==T-<stem>== /
# ==T-END== framing the Go path produced, so fourth_run_chunk splits the stream
# unchanged. Rebuilt only when the flattener source changes (a bin-go bootstrap;
# see the file header). The trailing fn-0 value + arm profile fkwu prints after
# ==T-END== falls outside every per-band marker range, so the split ignores it.
FOURTH_FLATTEN_TABLE="form-stdlib/fourth-flatten-table.txt"

fourth_available() { [[ -n "$FKWU" && -x "$FKWU" ]]; }

# fourth_selfhost — true when the committed flattener table is present, so the
# fourth arm flattens its own band tables on fkwu. Absent (a partial tree), the
# flatten falls back to the Go executor path so the suite degrades honestly.
# Gated to POSIX: on Windows fkwu's read_file reads source through a text-mode
# open() (CRLF-translated), so the self-flattened table diverges from the Go
# binary's. mac/linux self-host is proven four-way; the Windows self-host (a
# binary-mode read_file open) is a named follow-up — Windows keeps bin-go flatten.
fourth_selfhost() {
    [[ "${OS:-}" == "Windows_NT" || "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]] && return 1
    [[ -s "$FOURTH_FLATTEN_TABLE" && -n "$FKWU" && -x "$FKWU" ]]
}

# fourth_band_request — emit one band's request block for the flatten driver:
#   stem \n kind \n nmod \n <mod path>*nmod \n <band path>
# Modules are the shim (always first) then every non-band source in order; the
# last source is the band — matching fourth_flatten_expr's module/band split.
fourth_band_request() {
    local stem="$1" kind="$2"; shift 2
    local srcs=("$@") count last band i
    count="${#srcs[@]}"
    last=$((count - 1))
    band="${srcs[$last]}"
    local mods=("$FOURTH_SHIM")
    for ((i = 0; i < last; i++)); do mods+=("${srcs[$i]}"); done
    printf '%s\n%s\n%s\n' "$stem" "$kind" "${#mods[@]}"
    printf '%s\n' "${mods[@]}"
    printf '%s\n' "$band"
}

# Portable content hash for cache stamps. macOS ships `shasum`; Linux and Git
# Bash ship `sha256sum`; they don't overlap. The value is only ever a per-host
# cache key, so the algorithm is free — only availability matters.
fourth_hash16() {
    if command -v shasum >/dev/null 2>&1 && printf test | shasum >/dev/null 2>&1; then
        cat "$@" 2>/dev/null | shasum | cut -c1-16
    elif command -v sha1sum >/dev/null 2>&1 && printf test | sha1sum >/dev/null 2>&1; then
        cat "$@" 2>/dev/null | sha1sum | cut -c1-16
    elif command -v sha256sum >/dev/null 2>&1 && printf test | sha256sum >/dev/null 2>&1; then
        cat "$@" 2>/dev/null | sha256sum | cut -c1-16
    elif command -v cksum >/dev/null 2>&1 && printf test | cksum >/dev/null 2>&1; then
        cat "$@" 2>/dev/null | cksum | cut -c1-16
    else
        echo "fourth-arm.sh: need shasum, sha1sum, sha256sum, or cksum for cache keys" >&2
        return 1
    fi
}

# build_fourth — the standing fkwu binary, cached by emitter content.
build_fourth() {
    [[ -f "$FOURTH_MANIFEST" ]] || return 0
    command -v clang >/dev/null 2>&1 || return 0
    mkdir -p "$FOURTH_DIR"
    local stamp out tmp d is_windows
    local -a clang_args
    is_windows=0
    if [[ "${OS:-}" == "Windows_NT" || "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]; then
        is_windows=1
    fi
    stamp="$(fourth_hash16 "${FOURTH_CHAIN[@]}" "$GO_BIN")"
    out="$FOURTH_DIR/fkwu-$stamp"
    if [[ ! -x "$out" ]]; then
        echo "  building fourth kernel (fkwu)..." >&2
        d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth.XXXXXX")"
        cat form-stdlib/minimal-surface.fk form-stdlib/hati-os-kernel.fk \
            form-stdlib/hati-os-kernel-emit.fk > "$d/uni-driver.fk"
        cat >> "$d/uni-driver.fk" <<'EOF'
(do
  (print "==UNI==")
  (print (fkc-emit-universal))
  (print "==END==")
  0)
EOF
        "$GO_BIN" "$d/uni-driver.fk" 2>"$d/uni.err" > "$d/uni.out" || true
        sed -n '/^==UNI==$/,/^==END==$/p' "$d/uni.out" | sed -e '1d' -e '$d' > "$d/uni.c"
        if [[ "$is_windows" == "1" ]]; then
            sed -i '1i #define _CRT_SECURE_NO_WARNINGS 1' "$d/uni.c"
            sed -i 's|extern unsigned int arc4random(void);|extern int rand(void); static unsigned int arc4random(void) { return (unsigned int)rand(); }|' "$d/uni.c"
            sed -i 's|extern long long read(int, void \*, unsigned long);|extern int read(int, void *, unsigned int);|' "$d/uni.c"
            sed -i 's|extern long long write(long long, const void \*, unsigned long);|extern int write(int, const void *, unsigned int);|' "$d/uni.c"
            sed -i 's|mkdir(d, 0777)|mkdir(d)|g; s|mkdir(p, 0777)|mkdir(p)|g' "$d/uni.c"
            sed -i 's|extern int sprintf(char \*, const char \*, ...);|typedef __builtin_va_list fk_va_list; extern int vsnprintf(char *, unsigned long long, const char *, fk_va_list); static int sprintf(char *b, const char *fmt, ...) { fk_va_list ap; __builtin_va_start(ap, fmt); int n = vsnprintf(b, 4096ULL, fmt, ap); __builtin_va_end(ap); return n; }|' "$d/uni.c"
            sed -i 's|struct timeval { long tv_sec; int tv_usec; }; extern int gettimeofday(struct timeval \*, void \*);|struct timeval { long tv_sec; int tv_usec; }; struct fk_filetime { unsigned int dwLowDateTime; unsigned int dwHighDateTime; }; __declspec(dllimport) void __stdcall GetSystemTimeAsFileTime(struct fk_filetime *); static int gettimeofday(struct timeval *tv, void *tz) { (void)tz; struct fk_filetime ft; unsigned long long ticks; unsigned long long us; GetSystemTimeAsFileTime(\&ft); ticks = ((unsigned long long)ft.dwHighDateTime * 4294967296ULL) + (unsigned long long)ft.dwLowDateTime; us = (ticks / 10ULL) - 11644473600000000ULL; tv->tv_sec = (long)(us / 1000000ULL); tv->tv_usec = (int)(us % 1000000ULL); return 0; }|' "$d/uni.c"
            sed -i 's|extern void \*dlopen(const char \*, int); extern void \*dlsym(void \*, const char \*);|static void *dlopen(const char *p, int f) { (void)p; (void)f; return 0; } static void *dlsym(void *h, const char *s) { (void)h; (void)s; return 0; }|' "$d/uni.c"
            sed -i 's|getaddrinfo(host, port, \&hints, \&res)|fk_sock_getaddrinfo(host, port, \&hints, \&res)|g; s|fd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol)|fd = fk_sock_socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol)|g; s|connect(fd, rp->ai_addr, rp->ai_addrlen)|fk_sock_connect(fd, rp->ai_addr, rp->ai_addrlen)|g' "$d/uni.c"
            sed -i 's|read(fd, resp + total, 65535 - total)|fk_sock_read(fd, resp + total, 65535 - total)|g; s|write(fd, req + wr, rn - wr)|fk_sock_write(fd, req + wr, rn - wr)|g; s|write(fd, rptr + wr, rlen - wr)|fk_sock_write(fd, rptr + wr, rlen - wr)|g; s|close(fd);|fk_sock_close(fd);|g' "$d/uni.c"
        fi
        tmp="$(mktemp "$FOURTH_DIR/.fkwu-$stamp.XXXXXX")"
        clang_args=(
            -O2
            -Wno-error=implicit-function-declaration
            -Wno-implicit-function-declaration
            -Wno-incompatible-library-redeclaration
            -o "$tmp" "$d/uni.c"
        )
        if [[ "$is_windows" == "1" ]]; then
            clang_args+=(-lws2_32 -llegacy_stdio_definitions)
            # Windows default thread stack is 1 MiB — too small for the universal
            # walker's recursive descent on grammar-engine recipes (bmf-grammar,
            # form.bml cursor). The emitted main() keeps the main-thread entry on
            # Windows, so reserve 64 MiB for it so the cursor lane crosses the
            # fourth arm on Windows too, not only on Linux/macOS CI (8 MiB
            # default). Reserve is address space, committed lazily — no runtime cost.
            clang_args+=(-Xlinker /STACK:67108864)
        else
            # POSIX: the emitted main() runs fk_walk on a pthread sized to
            # FORM_KERNEL_STACK_MB (the stack-depth floor its siblings already
            # stand on) — link the pthread carrier so it resolves across CI libc
            # versions. macOS folds it into libSystem; the flag is harmless there.
            clang_args+=(-pthread)
        fi
        if [[ -s "$d/uni.c" ]] && clang "${clang_args[@]}" 2>"$d/clang.err"; then
            mv -f "$tmp" "$out"
        elif [[ -s "$d/uni.c" && "$is_windows" == "1" ]] \
            && command -v gcc >/dev/null 2>&1 \
            && gcc -O2 -Wno-implicit-function-declaration -Wno-builtin-declaration-mismatch -o "$tmp" "$d/uni.c" -lws2_32 2>"$d/gcc.err"; then
            mv -f "$tmp" "$out"
        else
            rm -f "$tmp"
            if [[ ! -s "$d/uni.c" && -s "$d/uni.err" ]]; then
                sed -n '1,12p' "$d/uni.err" >&2
            elif [[ -s "$d/gcc.err" ]]; then
                sed -n '1,12p' "$d/gcc.err" >&2
            elif [[ -s "$d/clang.err" ]]; then
                sed -n '1,12p' "$d/clang.err" >&2
            fi
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
# Flattens on fkwu (the committed T_flat) on a cache miss, or through the Go
# executor when the self-host table is absent; empty output means the band runs
# three-kernel only this time.
fourth_table() {
    local stem="$1" kind key out d f srcs=()
    kind="$(awk -v b="$stem" '$1==b{print $2; exit}' "$FOURTH_MANIFEST")"
    [[ -n "$kind" ]] || return 0
    while IFS= read -r f; do srcs+=("$f"); done < <(fourth_prep_srcs "$stem")
    [[ "${#srcs[@]}" -ge 1 ]] || return 0
    key="$(fourth_hash16 "${srcs[@]}" "${FOURTH_CHAIN[@]}")"
    out="$FOURTH_DIR/t-$stem-$key.txt"
    if [[ ! -s "$out" ]]; then
        if fourth_selfhost; then
            # one-band request → fkwu walks T_flat → marker-framed table; the
            # trailing fn-0 value + arm profile sit past ==T-END==, outside the range.
            { printf '1\n'; fourth_band_request "$stem" "$kind" "${srcs[@]}"; } \
                | "$FKWU" "$FOURTH_FLATTEN_TABLE" 0 2>/dev/null \
                | sed -n "/^==T-${stem}==\$/,/^==T-END==\$/p" | sed -e '1d' -e '$d' > "$out.tmp"
            [[ -s "$out.tmp" ]] && mv -f "$out.tmp" "$out" || rm -f "$out.tmp"
        else
            d="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth-t.XXXXXX")"
            cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
            fourth_flatten_expr "$kind" "${srcs[@]}" >> "$d/driver.fk"
            "$GO_BIN" "$d/driver.fk" 2>/dev/null > "$out.tmp" && mv -f "$out.tmp" "$out" || rm -f "$out.tmp"
            rm -rf "$d"
        fi
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

# fourth_run_chunk — flatten ONE chunk in a single pass, then split the
# marker-delimited output into per-band tables.
#   driver: self-host → a batch request (nbands + per-band blocks) fkwu walks
#           through T_flat; Go path → FOURTH_CHAIN + (==T-stem==, flatten expr)*
#           + ==T-END==
#   plan:   one "stem<TAB>outpath" line per band, in driver order
# Both paths emit the same ==T-<stem>== / ==T-END== framing, so the split is
# identical (the self-host trailing fn-0 value + arm profile sit past ==T-END==).
# Self-contained (reads only its two files), so it runs safely as a background
# job: every table publishes atomically (mv -f "$cur.tmp" "$cur"), so parallel
# chunks never collide. A band whose flatten emits nothing leaves no table and
# runs three-kernel only — honest degradation, never a red suite.
fourth_run_chunk() {
    local driver="$1" plan="$2" out_all="$1.out"
    if fourth_selfhost; then
        "$FKWU" "$FOURTH_FLATTEN_TABLE" 0 < "$driver" 2>/dev/null > "$out_all" || true
    else
        "$GO_BIN" "$driver" 2>/dev/null > "$out_all" || true
    fi
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
# fourth_seal_chunk — close a chunk so fourth_run_chunk emits ==T-END==.
# Self-host: prepend the band count so the driver's stdin loop knows the batch
# size. Go path: append the literal end marker.
fourth_seal_chunk() {
    local driver="$1" n="$2" selfhost="$3"
    if [[ "$selfhost" -eq 1 ]]; then
        { printf '%s\n' "$n"; cat "$driver"; } > "$driver.req" && mv -f "$driver.req" "$driver"
    else
        printf '(print "==T-END==")\n' >> "$driver"
    fi
}

fourth_prepare_all() {
    fourth_available || return 0
    [[ -f "$FOURTH_MANIFEST" ]] || return 0
    local workdir stem kind key out missing=0 f srcs driver plan cidx=0 ccount=0
    local batch_max="${FOURTH_PREPARE_ALL_BATCH_MAX:-48}"
    local selfhost=0; fourth_selfhost && selfhost=1
    workdir="$(mktemp -d "${TMPDIR:-/tmp}/form-fourth-all.XXXXXX")"
    while read -r stem kind _; do
        [[ -z "$stem" || "$stem" == \#* ]] && continue
        srcs=()
        while IFS= read -r f; do srcs+=("$f"); done < <(fourth_prep_srcs "$stem")
        [[ "${#srcs[@]}" -ge 1 ]] || continue
        key="$(fourth_hash16 "${srcs[@]}" "${FOURTH_CHAIN[@]}")"
        out="$FOURTH_DIR/t-$stem-$key.txt"
        [[ -s "$out" ]] && continue
        missing=$((missing + 1))
        if [[ "$ccount" -eq 0 ]]; then        # open a fresh chunk driver + plan
            driver="$workdir/driver-$cidx.fk"; plan="$workdir/plan-$cidx.tsv"
            if [[ "$selfhost" -eq 1 ]]; then : > "$driver"; else cat "${FOURTH_CHAIN[@]}" > "$driver"; fi
            : > "$plan"
        fi
        if [[ "$selfhost" -eq 1 ]]; then
            fourth_band_request "$stem" "$kind" "${srcs[@]}" >> "$driver"
        else
            printf '(print "==T-%s==")\n' "$stem" >> "$driver"
            fourth_flatten_expr "$kind" "${srcs[@]}" >> "$driver"
        fi
        printf '%s\t%s\n' "$stem" "$out" >> "$plan"
        ccount=$((ccount + 1))
        if [[ "$ccount" -ge "$batch_max" ]]; then   # seal a full chunk
            fourth_seal_chunk "$driver" "$ccount" "$selfhost"
            cidx=$((cidx + 1)); ccount=0
        fi
    done < "$FOURTH_MANIFEST"
    if [[ "$ccount" -gt 0 ]]; then               # seal the trailing partial chunk
        fourth_seal_chunk "$driver" "$ccount" "$selfhost"
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

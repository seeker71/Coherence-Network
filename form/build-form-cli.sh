#!/usr/bin/env bash
# build-form-cli.sh — produce the standalone native form-cli binary.
#
# Build-time honest floor (2026-06-24):
#   FLATTEN — committed bootstrap/form-cli-table.txt OR fkwu+T_flat self-host (no Go)
#   EMIT    — committed bootstrap/form-cli-emitted.c (no Go on receipt path)
#   LINK    — clang compiles C (pending: form-macho universal walker); skipped in FORM_STANDARD_LANE
# Maintainer regen (bin-go allowed off-receipt): scripts/regen_form_cli_bootstrap.sh
# Runtime: the resulting form-cli runs toolchain-free.
#
#   ./build-form-cli.sh            # -> form/form-cli
#   echo ping | ./form-cli        # -> pong   (no toolchain present)
#   ./form-cli                     # interactive REPL on a real tty
set -euo pipefail
cd "$(dirname "$0")"

S=form-stdlib
OUT="${1:-form-cli}"
CC_BIN="${CC:-clang}"
CLI_BOOTSTRAP_C="$S/bootstrap/form-cli-emitted.c"
CLI_BOOTSTRAP_STAMP="$S/bootstrap/form-cli.stamp"

if [[ "${FORM_STANDARD_LANE:-0}" == 1 && -x "$OUT" ]]; then
    echo "standard lane: $OUT present (no build)" >&2
    exit 0
fi

is_windows_host() {
    [[ "${OS:-}" == "Windows_NT" || "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* ]]
}

patch_windows_emitted_c() {
    local c_file="$1"
    sed -i '1i #define _CRT_SECURE_NO_WARNINGS 1' "$c_file"
    sed -i 's|extern unsigned int arc4random(void);|extern int rand(void); static unsigned int arc4random(void) { return (unsigned int)rand(); }|' "$c_file"
    sed -i 's|extern long long read(int, void \*, unsigned long);|extern int read(int, void *, unsigned int);|' "$c_file"
    sed -i 's|extern long long write(long long, const void \*, unsigned long);|extern int write(int, const void *, unsigned int);|' "$c_file"
    sed -i 's|mkdir(d, 0777)|mkdir(d)|g; s|mkdir(p, 0777)|mkdir(p)|g' "$c_file"
    sed -i 's|extern int sprintf(char \*, const char \*, ...);|typedef __builtin_va_list fk_va_list; extern int vsnprintf(char *, unsigned long long, const char *, fk_va_list); static int sprintf(char *b, const char *fmt, ...) { fk_va_list ap; __builtin_va_start(ap, fmt); int n = vsnprintf(b, 4096ULL, fmt, ap); __builtin_va_end(ap); return n; }|' "$c_file"
    sed -i 's|struct timeval { long tv_sec; int tv_usec; }; extern int gettimeofday(struct timeval \*, void \*);|struct timeval { long tv_sec; int tv_usec; }; struct fk_filetime { unsigned int dwLowDateTime; unsigned int dwHighDateTime; }; __declspec(dllimport) void __stdcall GetSystemTimeAsFileTime(struct fk_filetime *); static int gettimeofday(struct timeval *tv, void *tz) { (void)tz; struct fk_filetime ft; unsigned long long ticks; unsigned long long us; GetSystemTimeAsFileTime(\&ft); ticks = ((unsigned long long)ft.dwHighDateTime * 4294967296ULL) + (unsigned long long)ft.dwLowDateTime; us = (ticks / 10ULL) - 11644473600000000ULL; tv->tv_sec = (long)(us / 1000000ULL); tv->tv_usec = (int)(us % 1000000ULL); return 0; }|' "$c_file"
    sed -i 's|extern void \*dlopen(const char \*, int); extern void \*dlsym(void \*, const char \*);|static void *dlopen(const char *p, int f) { (void)p; (void)f; return 0; } static void *dlsym(void *h, const char *s) { (void)h; (void)s; return 0; }|' "$c_file"
}

if [[ "${FORM_STANDARD_LANE:-0}" != 1 ]]; then
    command -v "$CC_BIN" >/dev/null || { echo "${CC_BIN} is required at BUILD time (not at run time)"; exit 1; }
fi

W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT

# the emit chain (plain Form) + the flatten chain.
EMIT_CHAIN="$S/minimal-surface.fk $S/hati-os-kernel.fk $S/host-io-fs-fkwu-emit.fk $S/fkc-table-serialize.fk $S/hati-os-kernel-emit.fk"
FLAT_CHAIN="$EMIT_CHAIN $S/form-parse.fk $S/form-flatten.fk"
# The ask lane routes through http-fetch over the socket host-call floor for
# plaintext HTTP, so it must be defined before the dispatcher that routes to it.
MODS="(list (read_file \"$S/fourth-shim.fk\") (read_file \"$S/core.fk\") (read_file \"$S/resource-port.fk\") (read_file \"$S/bml-native-interface-package-import.fk\") (read_file \"$S/hati-os-targets.fk\") (read_file \"$S/form-native-resource-interfaces.fk\") (read_file \"$S/http-client.fk\") (read_file \"$S/form-cli-ask.fk\") (read_file \"$S/line-grammar.fk\") (read_file \"$S/voice-traits.fk\") (read_file \"$S/nearest-shape.fk\") (read_file \"$S/co-learning.fk\") (read_file \"$S/co-learning-stream.fk\") (read_file \"$S/mesh-dispatch.fk\") (read_file \"$S/surprise-salience.fk\") (read_file \"$S/host-sense-organ.fk\") (read_file \"$S/speech-organ.fk\") (read_file \"$S/native-host-instance.fk\") (read_file \"$S/text-tokenize.fk\") (read_file \"$S/rag-embed.fk\") (read_file \"$S/rag-index-codec.fk\") (read_file \"$S/rag-retrieve.fk\") (read_file \"$S/rag-ask.fk\") (read_file \"$S/form-cli.fk\"))"
BAND="(read_file \"$S/form-cli-repl.fk\")"

# Prefer fkwu self-host flatten (no Go) when T_flat + cached fkwu are warm.
FORM_CLI_SRCS=(
    "$S/fourth-shim.fk" "$S/core.fk" "$S/resource-port.fk"
    "$S/bml-native-interface-package-import.fk" "$S/hati-os-targets.fk"
    "$S/form-native-resource-interfaces.fk" "$S/http-client.fk"
    "$S/form-cli-ask.fk" "$S/line-grammar.fk" "$S/voice-traits.fk"
    "$S/nearest-shape.fk" "$S/co-learning.fk" "$S/co-learning-stream.fk"
    "$S/mesh-dispatch.fk" "$S/surprise-salience.fk" "$S/host-sense-organ.fk"
    "$S/speech-organ.fk" "$S/native-host-instance.fk"
    "$S/text-tokenize.fk" "$S/rag-embed.fk" "$S/rag-index-codec.fk" "$S/rag-retrieve.fk" "$S/rag-ask.fk"
    "$S/form-cli.fk"
    "$S/form-cli-repl.fk"
)
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh
slug="$(fourth_platform_slug)"
CLI_BOOTSTRAP_BIN="$S/bootstrap/form-cli-${slug}"
CLI_BOOTSTRAP_BIN_STAMP="$S/bootstrap/form-cli-${slug}.stamp"
stamp="$(fourth_fkwu_cache_stamp)"
cached_fkwu="$FOURTH_DIR/fkwu-$stamp"
[[ -x "$cached_fkwu" ]] && FKWU="$cached_fkwu"
if [[ -z "${FKWU:-}" ]]; then
    if [[ "${FORM_STANDARD_LANE:-0}" == 1 ]]; then
        build_fourth
    else
        build_fourth >/dev/null 2>&1 || true
    fi
fi

want_cli_stamp="$(fourth_hash16 "${FORM_CLI_SRCS[@]}")"

# Standard lane: copy committed platform binary when stamp matches (no clang).
if [[ "${FORM_STANDARD_LANE:-0}" == 1 ]]; then
    got_cli_boot="$(cat "$CLI_BOOTSTRAP_BIN_STAMP" 2>/dev/null || true)"
    if [[ -x "$CLI_BOOTSTRAP_BIN" && "$got_cli_boot" == "$want_cli_stamp" ]]; then
        cp "$CLI_BOOTSTRAP_BIN" "$OUT"
        chmod +x "$OUT"
        echo "standard lane: $OUT from bootstrap/${slug} (no clang)" >&2
        exit 0
    fi
    echo "standard lane: bootstrap form-cli-${slug} missing or stale" >&2
    exit 1
fi

# Warm path: copy platform binary before invoking clang when available.
got_cli_boot="$(cat "$CLI_BOOTSTRAP_BIN_STAMP" 2>/dev/null || true)"
if [[ -x "$CLI_BOOTSTRAP_BIN" && "$got_cli_boot" == "$want_cli_stamp" ]]; then
    cp "$CLI_BOOTSTRAP_BIN" "$OUT"
    chmod +x "$OUT"
    echo "  link: bootstrap form-cli-${slug} (no clang)" >&2
    exit 0
fi

# 1. flatten form-cli-repl into its program table (string pool rides behind it).
if [[ -s "$S/bootstrap/form-cli-table.txt" && "$(cat "$CLI_BOOTSTRAP_STAMP" 2>/dev/null)" == "$want_cli_stamp" ]]; then
    cp "$S/bootstrap/form-cli-table.txt" "$W/table.txt"
    echo "  flatten: bootstrap table (no Go)" >&2
elif fourth_selfhost && fourth_flatten_sources form-cli-build fks "$W/table.txt" "${FORM_CLI_SRCS[@]}"; then
    echo "  flatten: fkwu self-host (no Go)" >&2
else
    echo "  flatten: unavailable — need bootstrap/form-cli-table.txt or T_flat self-host (maintainer: scripts/regen_form_cli_bootstrap.sh)" >&2
    exit 1
fi
[[ -s "$W/table.txt" ]] || { echo "flatten produced no table"; exit 1; }

# 2. emit the combined walker with the table baked in (fk_prog).
if [[ -s "$CLI_BOOTSTRAP_C" && "$(cat "$CLI_BOOTSTRAP_STAMP" 2>/dev/null)" == "$want_cli_stamp" ]]; then
    cp "$CLI_BOOTSTRAP_C" "$W/form-cli.c"
    echo "  emit: bootstrap (no Go)" >&2
else
    echo "  emit: unavailable — need bootstrap/form-cli-emitted.c (maintainer: scripts/regen_form_cli_bootstrap.sh)" >&2
    exit 1
fi
grep -q fk_prog "$W/form-cli.c" || { echo "emit missing baked program"; exit 1; }

# 3. bake the GENESIS — this binary's own Form source — so 'form-cli source' can
#    print it and you can rebuild from the binary alone. It's the file-marked
#    concatenation of every recipe the build reads plus this script, appended as a
#    byte array (escape-free) and read at runtime by self_source (walker tag 117).
SOURCES="minimal-surface hati-os-kernel fkc-table-serialize hati-os-kernel-emit form-parse form-flatten core fourth-shim resource-port bml-native-interface-package-import hati-os-targets form-native-resource-interfaces http-client form-cli-ask line-grammar voice-traits nearest-shape co-learning co-learning-stream mesh-dispatch surprise-salience host-sense-organ speech-organ native-host-instance form-cli form-cli-main form-cli-repl"
{
  for f in $SOURCES; do printf ';;;; ==== FILE: %s/%s.fk ====\n' "$S" "$f"; cat "$S/$f.fk"; done
  printf ';;;; ==== FILE: build-form-cli.sh ====\n'; cat "$(basename "$0")"
} > "$W/genesis.txt"
GEN_LEN=$(wc -c < "$W/genesis.txt" | tr -d ' ')
{
  printf '\nconst unsigned char fk_genesis[] = {'
  od -An -v -tu1 "$W/genesis.txt" | tr -s ' \n' ',' | sed 's/^,//; s/,$//'
  printf '};\nconst long long fk_genesis_len = %s;\n' "$GEN_LEN"
} >> "$W/form-cli.c"

# 4. compile once -> the standalone native binary (program + own source baked in).
if [[ "${FORM_STANDARD_LANE:-0}" == 1 ]]; then
    echo "standard lane: skip clang link (use warmed $OUT)" >&2
    exit 0
fi
out_dir="$(dirname "$OUT")"
[[ "$out_dir" == "." ]] || mkdir -p "$out_dir"
clang_args=(
  -O2
  -Wno-error=implicit-function-declaration
  -Wno-implicit-function-declaration
  -Wno-incompatible-library-redeclaration
  -o "$OUT" "$W/form-cli.c"
)
if is_windows_host; then
  patch_windows_emitted_c "$W/form-cli.c"
  clang_args+=(-lws2_32 -llegacy_stdio_definitions)
fi
"$CC_BIN" "${clang_args[@]}"
echo "built $OUT  ($(wc -c < "$OUT") bytes, self-contained — runs with no Go/clang/table; carries ${GEN_LEN}B of its own source)"

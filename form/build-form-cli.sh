#!/usr/bin/env bash
# build-form-cli.sh — produce the standalone native form-cli binary.
#
# Build-time uses the bootstrap kernel (to flatten form-cli + emit the C) and
# clang (to compile) ONCE. The result — form/form-cli — is self-contained: it
# runs directly with NO Go, NO clang, NO C source, NO table file, nothing but the
# native binary and stdin. The form-cli program is baked into the binary as
# fk_prog (see fkc-emit-combined-repl in form-stdlib/hati-os-kernel-emit.fk).
#
#   ./build-form-cli.sh            # -> form/form-cli
#   echo ping | ./form-cli        # -> pong   (no toolchain present)
#   ./form-cli                     # interactive REPL on a real tty
set -euo pipefail
cd "$(dirname "$0")"

S=form-stdlib
GB=form-kernel-go/bin-go
OUT="${1:-form-cli}"
CC_BIN="${CC:-clang}"

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

[[ -x "$GB" ]] || ( echo "building bootstrap kernel..."; cd form-kernel-go && go build -o bin-go . )
command -v "$CC_BIN" >/dev/null || { echo "${CC_BIN} is required at BUILD time (not at run time)"; exit 1; }

W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT

# the emit chain (plain Form) + the flatten chain.
EMIT_CHAIN="$S/minimal-surface.fk $S/hati-os-kernel.fk $S/hati-os-kernel-emit.fk"
FLAT_CHAIN="$EMIT_CHAIN $S/form-parse.fk $S/form-flatten.fk"
# The ask lane routes through http-fetch over the socket host-call floor for
# plaintext HTTP, so it must be defined before the dispatcher that routes to it.
MODS="(list (read_file \"$S/fourth-shim.fk\") (read_file \"$S/core.fk\") (read_file \"$S/http-client.fk\") (read_file \"$S/form-cli-ask.fk\") (read_file \"$S/line-grammar.fk\") (read_file \"$S/voice-traits.fk\") (read_file \"$S/nearest-shape.fk\") (read_file \"$S/co-learning.fk\") (read_file \"$S/co-learning-stream.fk\") (read_file \"$S/mesh-dispatch.fk\") (read_file \"$S/surprise-salience.fk\") (read_file \"$S/host-sense-organ.fk\") (read_file \"$S/speech-organ.fk\") (read_file \"$S/native-host-instance.fk\") (read_file \"$S/form-cli.fk\"))"
BAND="(read_file \"$S/form-cli-repl.fk\")"

# 1. flatten form-cli-repl into its program table (string pool rides behind it).
echo "(fks-table-file (flt-band-sources-fns $MODS $BAND) (flt-band-sources-pool $MODS $BAND))" > "$W/flatten.fk"
"$GB" $FLAT_CHAIN "$W/flatten.fk" > "$W/table.txt"
[[ -s "$W/table.txt" ]] || { echo "flatten produced no table"; exit 1; }

# 2. emit the combined walker with the table baked in (fk_prog).
printf '(fkc-emit-combined-repl "%s")\n' "$(cat "$W/table.txt")" > "$W/emit.fk"
"$GB" $EMIT_CHAIN "$W/emit.fk" > "$W/form-cli.c"
grep -q fk_prog "$W/form-cli.c" || { echo "emit missing baked program"; exit 1; }

# 3. bake the GENESIS — this binary's own Form source — so 'form-cli source' can
#    print it and you can rebuild from the binary alone. It's the file-marked
#    concatenation of every recipe the build reads plus this script, appended as a
#    byte array (escape-free) and read at runtime by self_source (walker tag 117).
SOURCES="minimal-surface hati-os-kernel hati-os-kernel-emit form-parse form-flatten core fourth-shim http-client form-cli-ask line-grammar voice-traits nearest-shape co-learning co-learning-stream mesh-dispatch surprise-salience host-sense-organ speech-organ native-host-instance form-cli form-cli-main form-cli-repl"
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

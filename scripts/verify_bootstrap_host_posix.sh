#!/usr/bin/env bash
# Prove the cross-platform bootstrap host on macOS/Linux/Android(Termux) — the POSIX twin of verify_cross_platform_bootstrap_host_no_go.ps1.
#
# scripts/verify_cross_platform_bootstrap_host_no_go.ps1 is the Windows lane this mirrors.
#
# Proves the cross-platform bootstrap host (form/native/bootstrap/form_bootstrap_host.c)
# on macOS / Linux / Android (Termux): compile the tiny C host, build three swappable
# `recipe` dynamic libraries, dlopen-swap them behind the same symbol, assert the
# results, and confirm the measurement fields (loader == dlopen/dlsym).
#
# Scope, named honestly: this verifies the HOST + OS loader + swap contract — the
# same thing the Windows .ps1 verifies (whose recipe bytes are hand-built, not Form).
# The Form-emits-the-object-BYTES claim is a SEPARATE lane, proven four-way by the
# form-macho / form-elf bands and run end-to-end on arm64 macOS by
# scripts/form_macho_demo.sh. This script does not re-make that claim; it proves the
# bootstrap exe can load and swap recipe libraries behind one ABI on this OS.
#
# Exit 0 = pass OR honest skip (no compiler / wrong platform). Exit 1 = real failure.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/form/native/bootstrap/form_bootstrap_host.c"
WORK="${1:-$REPO/.cache/bootstrap-host-posix}"

uname_s="$(uname -s 2>/dev/null || echo unknown)"
uname_o="$(uname -o 2>/dev/null || echo unknown)"

# Windows shells (MSYS/MINGW/Cygwin) belong to the .ps1 lane.
case "$uname_s" in
    MINGW*|MSYS*|CYGWIN*)
        echo "SKIP: this is the POSIX twin; on Windows run scripts/verify_cross_platform_bootstrap_host_no_go.ps1"
        exit 0
        ;;
esac

[ -f "$SRC" ] || { echo "FAIL: missing host source $SRC"; exit 1; }

# Dynamic-library shape per OS.
is_macos=0
if [ "$uname_s" = "Darwin" ]; then is_macos=1; fi
is_android=0
if [ "$uname_o" = "Android" ] || [ -n "${TERMUX_VERSION:-}" ] || [ -d "/system/bin" ]; then is_android=1; fi

if [ "$is_macos" = "1" ]; then
    DLEXT="dylib"; SHARED_FLAGS="-dynamiclib"
else
    DLEXT="so"; SHARED_FLAGS="-shared -fPIC"
fi

# Find a C compiler.
CC=""
for cand in cc clang gcc; do
    if command -v "$cand" >/dev/null 2>&1; then CC="$cand"; break; fi
done
if [ -z "$CC" ]; then
    plat="$uname_s"; [ "$is_android" = "1" ] && plat="Android(Termux)"
    echo "SKIP: no C compiler (cc/clang/gcc) on PATH — install one to run the $plat bootstrap lane"
    echo "      (Termux: pkg install clang · Debian/Ubuntu: apt install build-essential · macOS: xcode-select --install)"
    exit 0
fi

mkdir -p "$WORK"
EXE="$WORK/form-bootstrap-host"

if ! "$CC" "$SRC" -O2 -o "$EXE" 2>"$WORK/host-compile.err"; then
    echo "FAIL: host compile failed:"; cat "$WORK/host-compile.err"; exit 1
fi

# Build one swappable recipe library. Each exports the same `recipe` symbol; only
# the body differs — that is the swap contract under test.
build_recipe() {
    name="$1"; body="$2"
    csrc="$WORK/$name.c"; lib="$WORK/$name.$DLEXT"
    cat > "$csrc" <<EOF
#include <stdint.h>
__attribute__((visibility("default"))) int64_t recipe(int64_t x) { return $body; }
EOF
    if ! "$CC" $SHARED_FLAGS "$csrc" -o "$lib" 2>"$WORK/$name.err"; then
        echo "FAIL: link failed for $name:"; cat "$WORK/$name.err"; return 1
    fi
    # macOS arm64 wants a signature on loadable code; ad-hoc is enough. Harmless elsewhere.
    if [ "$is_macos" = "1" ] && command -v codesign >/dev/null 2>&1; then
        codesign -s - -f "$lib" >/dev/null 2>&1 || true
    fi
    echo "$lib"
}

call_host() { # lib arg  -> trimmed stdout
    out="$("$EXE" "$1" recipe "$2" 2>"$WORK/call.err")" || {
        echo "FAIL: host call failed for $1 arg=$2:"; cat "$WORK/call.err"; return 1
    }
    printf '%s' "$out" | tr -d '[:space:]'
}

libA="$(build_recipe recipe_mul3_add7 "3 * x + 7")" || exit 1
libB="$(build_recipe recipe_mul5_add1 "5 * x + 1")" || exit 1
libC="$(build_recipe recipe_add42     "x + 42")"     || exit 1

rA="$(call_host "$libA" 5)" || exit 1
rB="$(call_host "$libB" 5)" || exit 1
rC="$(call_host "$libC" 9)" || exit 1
[ "$rA" = "22" ] || { echo "FAIL: recipe A returned $rA, want 22"; exit 1; }
[ "$rB" = "26" ] || { echo "FAIL: recipe B returned $rB, want 26"; exit 1; }
[ "$rC" = "51" ] || { echo "FAIL: recipe C returned $rC, want 51"; exit 1; }

# Measurement pass.
measured="$(FORM_BOOTSTRAP_MEASURE=1 "$EXE" "$libC" recipe 9 2>"$WORK/measure.err")" || {
    echo "FAIL: measured host call failed:"; cat "$WORK/measure.err"; exit 1
}
get_field() { printf '%s\n' "$measured" | awk -F= -v k="$1" '$1==k{print $2; exit}'; }
for key in result boundary primitive loader load_ns resolve_ns call_ns total_ns; do
    if [ -z "$(get_field "$key")" ]; then echo "FAIL: missing measured field $key"; exit 1; fi
done
[ "$(get_field result)" = "51" ] || { echo "FAIL: measured result $(get_field result), want 51"; exit 1; }
[ "$(get_field boundary)" = "form-native-to-host-os-loader" ] || { echo "FAIL: wrong boundary $(get_field boundary)"; exit 1; }
[ "$(get_field primitive)" = "dynamic-library-call" ] || { echo "FAIL: wrong primitive $(get_field primitive)"; exit 1; }
[ "$(get_field loader)" = "dlopen/dlsym" ] || { echo "FAIL: wrong loader $(get_field loader)"; exit 1; }

os_label="$uname_s"; [ "$is_android" = "1" ] && os_label="Android"
cat <<EOF
{
  "status": "pass",
  "os": "$os_label",
  "arch": "$(uname -m 2>/dev/null || echo unknown)",
  "dl_ext": "$DLEXT",
  "host": "$EXE",
  "compiler": "$(command -v "$CC")",
  "recipes": { "mul3_add7_arg5": $rA, "mul5_add1_arg5": $rB, "add42_arg9": $rC },
  "measurement": {
    "result": "$(get_field result)",
    "loader": "$(get_field loader)",
    "load_ns": "$(get_field load_ns)",
    "resolve_ns": "$(get_field resolve_ns)",
    "call_ns": "$(get_field call_ns)",
    "total_ns": "$(get_field total_ns)"
  }
}
EOF

#!/usr/bin/env bash
# build-android-fkwu.sh — cross-compile the C-bootstrapped fkwu universal kernel for
# Android ARM64 and stage the Form sense tables, so LiveSenseActivity runs the sense
# recipes natively on the phone. Two tables are staged:
#   loop-table.txt    — form-eval-cli-loop (the meta-circular eval) for the simple
#                       presence/surprise decisions: (if (le thr luma) 1 0).
#   observe-table.txt — live-observe-cli flattened WITH the rich sense recipes as
#                       preludes (presence-feature + scene-features + fused-observation):
#                       the camera-native fused observation (present/occupancy/where),
#                       proven four-way at validate.sh (live-observe band -> 127) and
#                       witnessed native on this phone. who/what stay un-witnessed on a
#                       camera-only frame (no face/mic organ), named so, never faked.
#
# The kernel binary is gitignored (*.so): it is a regenerable artifact, never a
# committed blob — the same convention as build-android-form-cli.sh. The body is
# runtime/fkwu-uni.c in the coherence-kernel repo; this only emits the carrier.
set -euo pipefail

APP="$(cd "$(dirname "$0")" && pwd)"
FORM="$(cd "$APP/../.." && pwd)/form"
# The clean kernel repo lives beside Coherence-Network by default; override with KERNEL_ROOT.
KERNEL_ROOT="${KERNEL_ROOT:-$(cd "$APP/../../.." && pwd)/coherence-kernel}"
KERNEL_SRC="$KERNEL_ROOT/runtime/fkwu-uni.c"
LOOP_TABLE="${LOOP_TABLE:-$KERNEL_ROOT/flatten/loop-table.txt}"

OUT="$APP/app/src/main/jniLibs/arm64-v8a/libfkwu_exec.so"
ASSET_TABLE="$APP/app/src/main/assets/native/loop-table.txt"
OBSERVE_TABLE="$APP/app/src/main/assets/native/observe-table.txt"

[[ -f "$KERNEL_SRC" ]] || { echo "kernel source not found: $KERNEL_SRC (set KERNEL_ROOT)"; exit 1; }

NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
[[ -d "$NDK" ]] || { echo "Android NDK not found — brew install android-ndk"; exit 1; }

case "$(uname -s)-$(uname -m)" in
    Darwin-*) HOST_TAG="darwin-x86_64" ;;
    Linux-x86_64) HOST_TAG="linux-x86_64" ;;
    *) echo "Unsupported NDK host: $(uname -s)-$(uname -m)" >&2; exit 2 ;;
esac
CC="$NDK/toolchains/llvm/prebuilt/$HOST_TAG/bin/aarch64-linux-android34-clang"
[[ -x "$CC" ]] || { echo "Android ARM64 clang not found at $CC"; exit 1; }

mkdir -p "$(dirname "$OUT")" "$(dirname "$ASSET_TABLE")"
"$CC" -O2 -pthread "$KERNEL_SRC" -o "$OUT"
case "$(file "$OUT")" in
    *"ELF 64-bit"*"ARM aarch64"*) echo "✓ Android fkwu → $OUT" ;;
    *) echo "✗ expected Android ARM64 ELF at $OUT"; file "$OUT"; exit 1 ;;
esac

# Stage the loop-table (the form-eval read-eval table fkwu walks). If a freshly
# flattened table exists in the kernel repo, prefer it; else keep the staged asset.
if [[ -f "$LOOP_TABLE" ]]; then
    cp "$LOOP_TABLE" "$ASSET_TABLE"
    echo "✓ loop-table asset ← $LOOP_TABLE"
elif [[ -f "$ASSET_TABLE" ]]; then
    echo "• reusing staged loop-table asset: $ASSET_TABLE"
else
    echo "✗ no loop-table available (set LOOP_TABLE to a flattened form-eval table)"; exit 1
fi

# Flatten the rich observe-table: live-observe-cli + the sense recipes as preludes,
# through the Form flattener (form-flatten.fk) executed by the bin-go BOOTSTRAP. bin-go
# is the flattener's executor only (never the runtime) — the same role it played for
# loop-table; the emitted table then runs on fkwu with no Go on device. Reproducible:
#   bin-go (FOURTH_CHAIN) '(print (fks-table-file (flt-band-sources-fns (list <shim+preludes>) <cli>) ...))'
flatten_observe_table() {
    local go_bin="$FORM/form-kernel-go/bin-go"
    if [[ ! -x "$go_bin" ]]; then
        ( cd "$FORM/form-kernel-go" && go build -o bin-go . ) || { echo "• bin-go build failed — reusing staged observe-table"; return 0; }
    fi
    local S="$FORM/form-stdlib"
    local chain=("$S/minimal-surface.fk" "$S/hati-os-kernel.fk" "$S/host-io-fs-fkwu-emit.fk" \
                 "$S/fkc-table-serialize.fk" "$S/hati-os-kernel-emit.fk" "$S/form-parse.fk" \
                 "$S/form-flatten.fk" "$S/fourth-shim.fk")
    local pre=("$S/fourth-shim.fk" "$S/core.fk" "$S/input-stream.fk" "$S/presence-feature.fk" \
               "$S/scene-features.fk" "$S/spatial-fusion.fk" "$S/confidence-weighted-vote.fk" \
               "$S/mesh-sense-7w.fk" "$S/fused-observation.fk" "$S/live-observe.fk")
    local band="$S/live-observe-cli.fk"
    local mods="" f
    for f in "${pre[@]}"; do mods="$mods (read_file \"$f\")"; done
    local d; d="$(mktemp -d "${TMPDIR:-/tmp}/observe-flat.XXXXXX")"
    cat "${chain[@]}" > "$d/driver.fk"
    printf '(print (fks-table-file (flt-band-sources-fns (list%s) (read_file "%s")) (flt-band-sources-pool (list%s) (read_file "%s"))))\n' \
        "$mods" "$band" "$mods" "$band" >> "$d/driver.fk"
    if "$go_bin" "$d/driver.fk" 2>"$d/err" > "$d/table.txt" && [[ -s "$d/table.txt" ]]; then
        cp "$d/table.txt" "$OBSERVE_TABLE"
        echo "✓ observe-table flattened ← live-observe-cli + sense recipes ($(wc -c < "$OBSERVE_TABLE" | tr -d ' ') bytes)"
    elif [[ -f "$OBSERVE_TABLE" ]]; then
        echo "• observe-table flatten failed — reusing staged asset"; head -2 "$d/err" >&2 || true
    else
        echo "✗ no observe-table available and flatten failed"; head -5 "$d/err" >&2; rm -rf "$d"; exit 1
    fi
    rm -rf "$d"
}
flatten_observe_table

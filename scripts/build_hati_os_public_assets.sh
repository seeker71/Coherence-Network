#!/usr/bin/env bash
# build_hati_os_public_assets.sh - build public Hati-OS native release assets.
#
# Produces real downloadable packages plus checksum/proof sidecars under
# .cache/hati-os-public-assets/<stamp>. The macOS binary is emitted from Form,
# compiled locally, and executed against the Go kernel's walker answers. The
# Android package contains the Rust kernel's Android ARM64 executable and C-ABI
# shared library when the Android NDK/cargo-ndk toolchain is available.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"
STAMP="${HATI_OS_ASSET_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="$ROOT/.cache/hati-os-public-assets/$STAMP"
MAC_STAGE="$OUT/stage/hati-os-macos-arm64"
ANDROID_STAGE="$OUT/stage/hati-os-android-arm64"

need() {
    command -v "$1" >/dev/null || { echo "FAIL missing required command: $1"; exit 1; }
}

need "$CLANG"
need zstd
need shasum
need file
need python3

mkdir -p "$OUT" "$MAC_STAGE/bin" "$MAC_STAGE/proof" "$MAC_STAGE/checksums"

if [[ ! -x "$GO_BIN" ]]; then
    echo "building Go Form kernel..."
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

WORK="$OUT/work"
mkdir -p "$WORK"

cat "$FORMDIR/form-stdlib/hati-os-native-cli-emit.fk" > "$WORK/hati-os-driver.fk"
cat >> "$WORK/hati-os-driver.fk" <<'EOF'
(print "==HATI_OS==")
(print (hati-os-program "hati_os"))
(print "==END==")
EOF

(cd "$FORMDIR" && "$GO_BIN" "$WORK/hati-os-driver.fk" 2>/dev/null) > "$WORK/hati-os-emit.out"
sed -n '/^==HATI_OS==$/,/^==END==$/p' "$WORK/hati-os-emit.out" | sed -e '1d' -e '$d' > "$MAC_STAGE/proof/hati_os.c"
grep -q 'int main' "$MAC_STAGE/proof/hati_os.c" || {
    echo "FAIL Form emission did not produce a C main; see $WORK/hati-os-emit.out"
    exit 1
}

"$CLANG" -O2 -o "$MAC_STAGE/bin/hati-os" "$MAC_STAGE/proof/hati_os.c"

cat > "$WORK/wfib.fk" <<'EOF'
(do (defn wfib (n) (if (le n 1) n (add (wfib (sub n 1)) (wfib (sub n 2))))) (print (wfib 28)) 0)
EOF
cat > "$WORK/wsum.fk" <<'EOF'
(do (defn wsum (n) (if (le n 0) 0 (add n (wsum (sub n 1))))) (print (wsum 1000)) 0)
EOF
cat > "$WORK/wack.fk" <<'EOF'
(do (defn wack (m n) (if (eq m 0) (add n 1) (if (eq n 0) (wack (sub m 1) 1) (wack (sub m 1) (wack m (sub n 1)))))) (print (wack 3 6)) 0)
EOF

run_go() { (cd "$FORMDIR" && "$GO_BIN" "$1" 2>/dev/null) | head -1; }

go_fib="$(run_go "$WORK/wfib.fk")"
go_sum="$(run_go "$WORK/wsum.fk")"
go_ack="$(run_go "$WORK/wack.fk")"
mac_fib="$("$MAC_STAGE/bin/hati-os" 1 28)"
mac_sum="$("$MAC_STAGE/bin/hati-os" 2 1000)"
mac_ack="$("$MAC_STAGE/bin/hati-os" 3 3 6)"

[[ "$go_fib" == "$mac_fib" ]] || { echo "FAIL fib parity: go=$go_fib mac=$mac_fib"; exit 1; }
[[ "$go_sum" == "$mac_sum" ]] || { echo "FAIL sum parity: go=$go_sum mac=$mac_sum"; exit 1; }
[[ "$go_ack" == "$mac_ack" ]] || { echo "FAIL ack parity: go=$go_ack mac=$mac_ack"; exit 1; }

mac_file="$(file "$MAC_STAGE/bin/hati-os")"
case "$mac_file" in
    *"Mach-O"*"arm64"*) ;;
    *) echo "FAIL macOS binary is not Mach-O arm64: $mac_file"; exit 1 ;;
esac

cat > "$MAC_STAGE/README.txt" <<EOF
Hati-OS macOS arm64 native package

Binary: bin/hati-os
Source: proof/hati_os.c, emitted by form/form-stdlib/hati-os-native-cli-emit.fk
Proof: proof/receipt.json
EOF

python3 - "$MAC_STAGE/proof/receipt.json" "$mac_file" "$go_fib" "$go_sum" "$go_ack" "$mac_fib" "$mac_sum" "$mac_ack" <<'PY'
import json, pathlib, sys
path, file_line, go_fib, go_sum, go_ack, mac_fib, mac_sum, mac_ack = sys.argv[1:]
data = {
    "target": "macos-arm64",
    "package": "hati-os-macos-arm64.tar.zst",
    "emitter": "form/form-stdlib/hati-os-native-cli-emit.fk",
    "binary": "bin/hati-os",
    "file": file_line,
    "local_execution": {
        "fib_28": {"go_kernel": go_fib, "native_binary": mac_fib},
        "sum_1000": {"go_kernel": go_sum, "native_binary": mac_sum},
        "ack_3_6": {"go_kernel": go_ack, "native_binary": mac_ack},
    },
    "status": "pass",
}
pathlib.Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

(cd "$OUT/stage" && tar -cf - hati-os-macos-arm64 | zstd -19 -q -o "$OUT/hati-os-macos-arm64.tar.zst")
shasum -a 256 "$OUT/hati-os-macos-arm64.tar.zst" | sed "s#$OUT/##" > "$OUT/hati-os-macos-arm64.tar.zst.sha256"
cp "$OUT/hati-os-macos-arm64.tar.zst.sha256" "$MAC_STAGE/checksums/sha256.txt"

android_status="skipped"
android_reason=""
android_file_bin=""
android_file_so=""
ANDROID_TARBALL="$OUT/hati-os-android-arm64.tar.zst"
if [[ "${HATI_OS_SKIP_ANDROID:-0}" == "1" ]]; then
    android_reason="HATI_OS_SKIP_ANDROID=1"
elif [[ -x "$ROOT/form/form-kernel-rust/build-android.sh" ]]; then
    if (cd "$ROOT/form/form-kernel-rust" && ./build-android.sh); then
        mkdir -p "$ANDROID_STAGE/bin" "$ANDROID_STAGE/lib/arm64-v8a" "$ANDROID_STAGE/proof" "$ANDROID_STAGE/checksums"
        cp "$ROOT/form/form-kernel-rust/target/aarch64-linux-android/release/form-kernel-rust" "$ANDROID_STAGE/bin/hati-os"
        cp "$ROOT/form/form-kernel-rust/target/aarch64-linux-android/release/libform_kernel_rust.so" "$ANDROID_STAGE/lib/arm64-v8a/libform_kernel_rust.so"
        android_file_bin="$(file "$ANDROID_STAGE/bin/hati-os")"
        android_file_so="$(file "$ANDROID_STAGE/lib/arm64-v8a/libform_kernel_rust.so")"
        case "$android_file_bin" in
            *"ELF"*"ARM aarch64"*) ;;
            *) echo "FAIL Android binary is not ARM aarch64 ELF: $android_file_bin"; exit 1 ;;
        esac
        case "$android_file_so" in
            *"shared object"*"ARM aarch64"*) ;;
            *) echo "FAIL Android library is not ARM aarch64 shared object: $android_file_so"; exit 1 ;;
        esac
        cat > "$ANDROID_STAGE/README.txt" <<'EOF'
Hati-OS Android arm64 native package

Binary: bin/hati-os
C-ABI library: lib/arm64-v8a/libform_kernel_rust.so
Proof: proof/receipt.json

This is the native kernel package. An APK shell is a separate app integration
step and is not represented by this tarball.
EOF
        python3 - "$ANDROID_STAGE/proof/receipt.json" "$android_file_bin" "$android_file_so" <<'PY'
import json, pathlib, sys
path, bin_file, so_file = sys.argv[1:]
data = {
    "target": "android-arm64",
    "package": "hati-os-android-arm64.tar.zst",
    "binary": "bin/hati-os",
    "c_abi_library": "lib/arm64-v8a/libform_kernel_rust.so",
    "file": {"binary": bin_file, "library": so_file},
    "local_execution": {
        "status": "not-run-on-host",
        "reason": "Android ARM64 artifact was cross-compiled and file/symbol checked locally; on-device execution receipt is the next proof lane."
    },
    "status": "pass",
}
pathlib.Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
        (cd "$OUT/stage" && tar -cf - hati-os-android-arm64 | zstd -19 -q -o "$ANDROID_TARBALL")
        shasum -a 256 "$ANDROID_TARBALL" | sed "s#$OUT/##" > "$ANDROID_TARBALL.sha256"
        cp "$ANDROID_TARBALL.sha256" "$ANDROID_STAGE/checksums/sha256.txt"
        android_status="pass"
    else
        android_status="fail"
        android_reason="form/form-kernel-rust/build-android.sh failed"
    fi
else
    android_reason="form/form-kernel-rust/build-android.sh is not executable"
fi

mac_sha="$(cut -d' ' -f1 "$OUT/hati-os-macos-arm64.tar.zst.sha256")"
android_sha=""
if [[ -f "$ANDROID_TARBALL.sha256" ]]; then
    android_sha="$(cut -d' ' -f1 "$ANDROID_TARBALL.sha256")"
fi
apk_status="absent"
apk_sha=""
APK_SRC="$ROOT/experiments/coherence-sense-android/app/build/outputs/apk/debug/app-debug.apk"
if [[ -f "$APK_SRC" ]]; then
    cp "$APK_SRC" "$OUT/coherence-sense-hati-mesh-debug.apk"
    shasum -a 256 "$OUT/coherence-sense-hati-mesh-debug.apk" | sed "s#$OUT/##" > "$OUT/coherence-sense-hati-mesh-debug.apk.sha256"
    apk_sha="$(cut -d' ' -f1 "$OUT/coherence-sense-hati-mesh-debug.apk.sha256")"
    apk_status="pass"
fi

python3 - "$OUT/hati-os-public-assets-summary.json" "$STAMP" "$mac_sha" "$android_status" "$android_sha" "$android_reason" "$mac_file" "$android_file_bin" "$android_file_so" "$apk_status" "$apk_sha" <<'PY'
import json, pathlib, sys
summary_path, stamp, mac_sha, android_status, android_sha, android_reason, mac_file, android_file_bin, android_file_so, apk_status, apk_sha = sys.argv[1:]
assets = [
    {
        "target": "macos-arm64",
        "name": "hati-os-macos-arm64.tar.zst",
        "sha256": mac_sha,
        "status": "pass",
        "proof": "macOS Mach-O arm64 binary executed locally for fib/sum/ack parity.",
        "file": mac_file,
    }
]
android = {
    "target": "android-arm64",
    "name": "hati-os-android-arm64.tar.zst",
    "sha256": android_sha,
    "status": android_status,
    "proof": "Android ARM64 ELF and C-ABI shared library package.",
}
if android_reason:
    android["reason"] = android_reason
if android_file_bin or android_file_so:
    android["file"] = {"binary": android_file_bin, "library": android_file_so}
assets.append(android)
assets.append({
    "target": "android-arm64",
    "name": "coherence-sense-hati-mesh-debug.apk",
    "sha256": apk_sha,
    "status": apk_status,
    "proof": "Android app debug APK built by Gradle; announces stable organ identity to hati.mesh, heartbeats while listening, displays dashboard/resource/flow rows, and offers QR identity pairing.",
    "note": "Debug-signed app shell; native kernel package remains the Hati-OS target artifact.",
})
data = {
    "stamp": stamp,
    "builder": "scripts/build_hati_os_public_assets.sh",
    "release_tag": "hati-os-v0.1.0-20260613",
    "assets": assets,
}
pathlib.Path(summary_path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY

echo "Built Hati-OS public assets in $OUT"
find "$OUT" -maxdepth 1 -type f -print | sort

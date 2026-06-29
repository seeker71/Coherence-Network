#!/bin/bash
# build.sh — compile the mac sensing carrier into a .app bundle with swiftc.
#
# The body (the fkwu (le ..) gates) is already native and bundled as Resources/native/
# (fkwu-mac arm64 + the proven loop-table.txt). This script only builds the thin Swift
# carrier (camera, UI, voice) around it and packages a proper .app with the camera
# usage-description plist so macOS will grant the eye.
#
# Reuses bundle id com.coherence.sense so an existing camera grant carries.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
APP="${1:-$HERE/build/CoherenceSense.app}"
NAME="CoherenceSense"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/native"

# 1. Bundle the proven native body (kernel + flattened recipe tables).
cp "$HERE/Resources/native/fkwu-mac"        "$APP/Contents/Resources/native/fkwu-mac"
cp "$HERE/Resources/native/loop-table.txt"  "$APP/Contents/Resources/native/loop-table.txt"
chmod +x "$APP/Contents/Resources/native/fkwu-mac"

# 1b. The presence-table: presence-cli flattened WITH presence-feature as prelude, through
#     the Form flattener (form-flatten.fk) run by the bin-go BOOTSTRAP. bin-go is the
#     flattener's executor only (never the runtime) — the emitted table runs on fkwu with no
#     Go on device. This carries the OCCUPANCY decision (pf-present? / pf-occupancy) that
#     replaces the auto-exposure-fooled luminance gate. Mirrors android's flatten_observe_table.
#     If the flatten can't run (no bin-go), the staged Resources/native/presence-table.txt is
#     reused — never silently dropped.
PRESENCE_TABLE="$APP/Contents/Resources/native/presence-table.txt"
flatten_presence_table() {
    local form="$HERE/../../form"
    local go_bin="$form/form-kernel-go/bin-go"
    if [[ ! -x "$go_bin" ]]; then
        ( cd "$form/form-kernel-go" && go build -o bin-go . ) \
            || { echo "• bin-go build failed — reusing staged presence-table"; return 0; }
    fi
    local S="$form/form-stdlib"
    local chain=("$S/minimal-surface.fk" "$S/hati-os-kernel.fk" "$S/host-io-fs-fkwu-emit.fk" \
                 "$S/fkc-table-serialize.fk" "$S/hati-os-kernel-emit.fk" "$S/form-parse.fk" \
                 "$S/form-flatten.fk" "$S/fourth-shim.fk")
    local pre=("$S/fourth-shim.fk" "$S/core.fk" "$S/presence-feature.fk")
    local band="$S/presence-cli.fk"
    local mods="" f
    for f in "${pre[@]}"; do mods="$mods (read_file \"$f\")"; done
    local d; d="$(mktemp -d "${TMPDIR:-/tmp}/presence-flat.XXXXXX")"
    cat "${chain[@]}" > "$d/driver.fk"
    printf '(print (fks-table-file (flt-band-sources-fns (list%s) (read_file "%s")) (flt-band-sources-pool (list%s) (read_file "%s"))))\n' \
        "$mods" "$band" "$mods" "$band" >> "$d/driver.fk"
    if "$go_bin" "$d/driver.fk" 2>"$d/err" > "$d/table.txt" && [[ -s "$d/table.txt" ]]; then
        cp "$d/table.txt" "$HERE/Resources/native/presence-table.txt"
        cp "$d/table.txt" "$PRESENCE_TABLE"
        echo "✓ presence-table flattened ← presence-cli + presence-feature ($(wc -c < "$PRESENCE_TABLE" | tr -d ' ') bytes)"
    elif [[ -f "$HERE/Resources/native/presence-table.txt" ]]; then
        cp "$HERE/Resources/native/presence-table.txt" "$PRESENCE_TABLE"
        echo "• presence-table flatten failed — reusing staged asset"; head -2 "$d/err" >&2 || true
    else
        echo "✗ no presence-table available and flatten failed"; head -5 "$d/err" >&2; rm -rf "$d"; exit 1
    fi
    rm -rf "$d"
}
flatten_presence_table

# 2. Info.plist (carries NSCameraUsageDescription + bundle id).
cp "$HERE/Info.plist" "$APP/Contents/Info.plist"

# 3. Compile the Swift carrier.
swiftc -O \
  -o "$APP/Contents/MacOS/$NAME" \
  "$HERE/Sources/FkwuSense.swift" \
  "$HERE/Sources/FieldRelay.swift" \
  "$HERE/Sources/Voice.swift" \
  "$HERE/Sources/Sensing.swift" \
  "$HERE/Sources/SenseApp.swift" \
  -framework SwiftUI -framework AppKit -framework AVFoundation -framework CoreImage \
  -framework Combine

# 4. Ad-hoc sign so the camera-permission prompt + TCC grant behave.
codesign --force --deep --sign - \
  --entitlements "$HERE/Sense.entitlements" \
  "$APP" 2>/dev/null || codesign --force --deep --sign - "$APP"

echo "built: $APP"

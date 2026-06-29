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

# 1. Bundle the proven native body (kernel + flattened recipe table).
cp "$HERE/Resources/native/fkwu-mac"        "$APP/Contents/Resources/native/fkwu-mac"
cp "$HERE/Resources/native/loop-table.txt"  "$APP/Contents/Resources/native/loop-table.txt"
chmod +x "$APP/Contents/Resources/native/fkwu-mac"

# 2. Info.plist (carries NSCameraUsageDescription + bundle id).
cp "$HERE/Info.plist" "$APP/Contents/Info.plist"

# 3. Compile the Swift carrier.
swiftc -O \
  -o "$APP/Contents/MacOS/$NAME" \
  "$HERE/Sources/FkwuSense.swift" \
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

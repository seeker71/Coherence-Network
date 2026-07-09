#!/usr/bin/env bash
# build-app.sh — build the native Sema Companion macOS app and bundle it as a .app you can
# double-click (or `open build/SemaCompanion.app`). No Xcode: SwiftPM + a hand-written
# bundle, the same lightweight lane as coherence-sense-mac.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

swift build -c release
BIN="$(swift build -c release --show-bin-path)/SemaCompanion"
APP="$HERE/build/SemaCompanion.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$BIN" "$APP/Contents/MacOS/SemaCompanion"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Sema Companion</string>
  <key>CFBundleDisplayName</key><string>Sema Companion</string>
  <key>CFBundleIdentifier</key><string>earth.hati.sema-companion</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>SemaCompanion</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

echo "built $APP"
echo "run: open \"$APP\""

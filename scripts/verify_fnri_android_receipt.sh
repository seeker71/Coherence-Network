#!/usr/bin/env bash
# verify_fnri_android_receipt.sh — fnri standard-receipt android runtime row (device).
#
# Runs form-native-resource-interfaces on a connected Android device via the
# existing verify_fkwu_android_no_go.sh carrier. Skips gracefully when no adb device.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WANT=32767
exec bash "$ROOT/scripts/verify_fkwu_android_no_go.sh" form-native-resource-interfaces

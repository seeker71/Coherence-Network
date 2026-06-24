#!/usr/bin/env bash
# verify_fnri_android_receipt.sh — fnri standard-receipt android runtime row (device).
#
# Runs fnri catalog + host-io + metal stand-in bands on a connected Android device
# via verify_fkwu_android_no_go.sh. Skips gracefully when no adb device.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/verify_fkwu_android_no_go.sh" \
  form-native-resource-interfaces \
  fnri-dispatch-carrier \
  fnri-host-io \
  fnri-audio-standin \
  fnri-video-standin \
  fnri-gpu-standin \
  fsh-fnri-staged

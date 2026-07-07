package com.coherence.sema.core

// The device-admin receiver that lets the app become DEVICE OWNER — the one
// privilege that makes self-update truly silent (no tap, ever, across reboots,
// no root). It is armed ONCE, from a computer, while the phone has no accounts:
//
//   adb shell dpm set-device-owner com.coherence.sema/.core.SemaDeviceAdminReceiver
//
// After that the PackageInstaller commit in SelfUpdate returns STATUS_SUCCESS
// with no UI. This receiver holds no policy of its own — it exists only to carry
// the device-owner grant; the app never locks, wipes, or restricts the device.

import android.app.admin.DeviceAdminReceiver

class SemaDeviceAdminReceiver : DeviceAdminReceiver()

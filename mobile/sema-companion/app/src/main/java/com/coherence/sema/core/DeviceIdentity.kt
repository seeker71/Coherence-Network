package com.coherence.sema.core

// device-identity: a stable id is the cell's NodeID at the device scale. ANDROID_ID is the
// device's own durable handle; every presence this phone announces is attributable to it.

import android.content.Context
import android.os.Build
import android.provider.Settings

object DeviceIdentity {
    @Volatile private var cached: String? = null

    fun id(context: Context): String {
        cached?.let { return it }
        val raw = try {
            Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        } catch (e: Exception) { null } ?: "unknown"
        val id = "andr-" + raw.take(8)
        cached = id
        return id
    }

    fun organId(context: Context): String = "sema-companion-" + id(context)

    // The human name shown on the mesh — the device's OWN name (Settings > About > Device
    // name, e.g. "Urs's S23 Ultra"), so the roster reads in the steward's words, never a
    // model number we invented. Falls back to the market/model name if the device is unnamed.
    fun displayName(context: Context): String {
        val native = try {
            Settings.Global.getString(context.contentResolver, Settings.Global.DEVICE_NAME)
        } catch (e: Exception) { null }
        return native?.takeIf { it.isNotBlank() }
            ?: listOf(Build.MANUFACTURER, Build.MODEL).filter { it.isNotBlank() }.joinToString(" ").ifBlank { "Android device" }
    }
}

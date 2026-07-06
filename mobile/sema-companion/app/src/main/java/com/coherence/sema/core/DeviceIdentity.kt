package com.coherence.sema.core

// device-identity: a stable id is the cell's NodeID at the device scale. ANDROID_ID is the
// device's own durable handle; every presence this phone announces is attributable to it.

import android.content.Context
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
}

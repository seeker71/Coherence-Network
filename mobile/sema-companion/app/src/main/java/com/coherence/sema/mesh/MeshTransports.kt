package com.coherence.sema.mesh

// MeshTransports — the process-wide registry of wired transports. Each is an adapter over
// an OS stack; the ladder (kernel observe/transport-ladder.fk) picks the best reachable
// one. Today the LAN/mDNS stack is wired and serving; the other stacks (wifi-direct,
// bluetooth, nfc, acoustic, optical) are the same shape of adapter waiting to be added
// here — each a small wiring job over an API Android already ships, not a radio to build.

import android.content.Context

object MeshTransports {
    private val transports = mutableListOf<MeshTransport>()

    fun startAll(context: Context, versionCode: Int) {
        if (transports.isNotEmpty()) return
        val app = context.applicationContext
        transports += LanMdnsTransport(app, versionCode)
        // wifi-direct, bluetooth, nfc, acoustic, optical adapters plug in here as they land.
        transports.forEach { runCatching { it.start() } }
    }

    fun reachable(id: String): Boolean = transports.firstOrNull { it.id == id }?.reachable() ?: false
}

package com.coherence.sema.data

// TransportLadder — the carrier mirror of the kernel cell observe/transport-ladder.fk
// (band 31). Every way two organs could reach each other, ranked; the ladder picks the
// best that is BOTH reachable now AND actually built. The cell is the authority; this
// only probes the real radios and reports status. The never-fabricate floor is the same:
// a transport we have only named (implemented=false) is never "usable", no matter how
// reachable — the Senses room shows it PENDING, not connected.
//
// Today only CLOUD_PROXY is built, and it already makes the mesh work regardless of
// whether the phone and Mac share a network (both reach api.coherencycoin.com over their
// own links). The other seven are the honest roadmap.

import android.bluetooth.BluetoothAdapter
import android.content.Context
import android.content.pm.PackageManager
import com.coherence.sema.mesh.MeshTransports
import java.net.HttpURLConnection
import java.net.URL

enum class Reach { UP, DOWN, PENDING }   // PENDING = the stack exists, the adapter is not wired yet

data class Transport(
    val id: String,
    val rank: Int,          // lower = preferred (direct/local/offline-capable first)
    val implemented: Boolean,
    val reach: Reach,
    val note: String,
) {
    val usable: Boolean get() = implemented && reach == Reach.UP
}

object TransportLadder {

    // Probe every channel. Built transports report a real UP/DOWN; unbuilt ones report
    // PENDING with whether the radio is even present on this device (honest, not faked).
    // NOTE: does network I/O (cloud reachability) — call off the main thread.
    fun probe(context: Context): List<Transport> {
        val hasBt = BluetoothAdapter.getDefaultAdapter() != null
        val pm = context.packageManager
        val hasNfc = pm.hasSystemFeature(PackageManager.FEATURE_NFC)
        val hasWifiDirect = pm.hasSystemFeature(PackageManager.FEATURE_WIFI_DIRECT)
        val hasMic = pm.hasSystemFeature(PackageManager.FEATURE_MICROPHONE)
        val hasCam = pm.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)
        fun pend(present: Boolean) = if (present) "stack present, adapter pending" else "no stack, pending"

        val lanUp = MeshTransports.reachable("lan-mdns")
        return listOf(
            Transport("wifi-direct", 1, false, Reach.PENDING, pend(hasWifiDirect)),
            Transport("wifi-mesh", 2, false, Reach.PENDING, pend(hasWifiDirect)),
            Transport("bluetooth", 3, false, Reach.PENDING, pend(hasBt)),
            Transport("nfc", 4, false, Reach.PENDING, pend(hasNfc)),
            Transport("acoustic", 5, false, Reach.PENDING, pend(hasMic)),          // speaker <-> mic
            Transport("optical", 6, false, Reach.PENDING, pend(hasCam)),           // screen <-> camera (QR)
            Transport(
                "lan-mdns", 7, true,
                if (lanUp) Reach.UP else Reach.DOWN,
                "NsdManager _sema-mesh._tcp — wired, advertising + serving a presence frame",
            ),
            Transport(
                "cloud-proxy", 8, true,
                if (cloudReachable()) Reach.UP else Reach.DOWN,
                "phone-network => public api; works across any network",
            ),
        )
    }

    // The best transport that is reachable AND built, or null (honest offline).
    fun best(context: Context): Transport? =
        probe(context).filter { it.usable }.minByOrNull { it.rank }

    // Resilience: how many independent usable ways to connect (>=2 = anastomotic).
    fun resilience(context: Context): Int = probe(context).count { it.usable }

    private fun cloudReachable(): Boolean = try {
        val c = (URL("https://api.coherencycoin.com/api/hati/mesh/organs?limit=1").openConnection() as HttpURLConnection)
        c.connectTimeout = 4000; c.readTimeout = 4000
        val ok = c.responseCode in 200..299
        c.disconnect(); ok
    } catch (e: Exception) { false }
}

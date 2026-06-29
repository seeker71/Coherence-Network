package com.coherence.sense

// FieldRelay — the Android-side cross-device transport (CARRIER, thin).
//
// The phone reaches the Mac's relay at 127.0.0.1:8777 over `adb reverse tcp:8777`
// — a clean USB tunnel, no wifi/firewall. This object only MOVES readings: it POSTs
// this device's reading and GETs the roster of the OTHER cells. It computes no
// verdict — fusion/surprise/trust all run in native fkwu (FkwuSense). The relay's
// routing DECISION lives in field-relay.fk on the Mac (content-blind + consent).
//
// device-identity: a stable id is the cell's NodeID at the device scale. ANDROID_ID
// is the device's own durable handle; we tag every reading with "andr-<id8>" so the
// Mac can attribute each reading to its real device (device-identity recipe).
//
// Reading wire shape (opaque to the relay): device|present|luma|surprise|kind

import android.content.Context
import android.provider.Settings
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object FieldRelay {
    private const val BASE = "http://127.0.0.1:8777"
    private const val KIND = "sense"  // the one signal-kind every cell offers (consent gate)

    @Volatile private var cachedId: String? = null

    // device-identity: this device's stable id (its NodeID at the device scale).
    fun deviceId(context: Context): String {
        cachedId?.let { return it }
        val raw = try {
            Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        } catch (e: Exception) { null } ?: "unknown"
        val id = "andr-" + raw.take(8)
        cachedId = id
        return id
    }

    data class Other(
        val device: String,
        val present: Boolean,
        val luma: Int,
        val surprise: Int,
        val kind: String,
        val ageMs: Long,
    )

    data class Exchange(
        val reached: Boolean,        // did the tunnel/relay actually respond?
        val others: List<Other>,     // the OTHER cells' readings
        val error: String? = null,
    )

    // POST this device's reading; the relay hands back the roster of the OTHER cells.
    // One real round-trip across the tunnel — the exchange that ends the islands.
    fun exchange(context: Context, present: Boolean, luma: Int, surprise: Int): Exchange {
        val dev = deviceId(context)
        val payload = "$dev|${if (present) 1 else 0}|$luma|$surprise|$KIND"
        return try {
            val url = URL("$BASE/reading")
            val c = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 1500
                readTimeout = 1500
                doOutput = true
                setRequestProperty("Content-Type", "text/plain")
            }
            OutputStreamWriter(c.outputStream).use { it.write(payload) }
            val code = c.responseCode
            if (code != 200) {
                return Exchange(reached = false, others = emptyList(),
                    error = "relay HTTP $code")
            }
            val body = c.inputStream.bufferedReader().readText().trim()
            Exchange(reached = true, others = parseRoster(body))
        } catch (e: Exception) {
            Exchange(reached = false, others = emptyList(),
                error = "${e.javaClass.simpleName}: ${e.message}")
        }
    }

    private fun parseRoster(body: String): List<Other> {
        if (body.isBlank()) return emptyList()
        return body.lineSequence().mapNotNull { line ->
            val p = line.split("|")
            if (p.size < 6) return@mapNotNull null
            try {
                Other(
                    device = p[0],
                    present = p[1] == "1",
                    luma = p[2].toInt(),
                    surprise = p[3].toInt(),
                    kind = p[4],
                    ageMs = p[5].toLong(),
                )
            } catch (e: Exception) { null }
        }.toList()
    }
}

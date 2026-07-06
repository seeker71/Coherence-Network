package com.coherence.sema.data

// The deployed membrane at api.coherencycoin.com — the same doors the cloud session crossed
// on 2026-07-06 (kernel receipt: first-membrane-crossing-cloud-presence). The phone arrives
// the same way: announce (seam in the identity), heartbeat while listening, offer channels
// (never pull), and read back who the mesh witnesses.

import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

data class MeshOrgan(
    val organId: String,
    val kind: String,
    val displayName: String,
    val dwelling: String,
    val listening: Boolean,
    val discoveryState: String,
    val capabilities: List<String>,
    val lanes: List<String>,
    val lastSeenAt: String,
)

data class MeshChannel(
    val from: String,
    val to: String,
    val protocol: String,
    val interfaceText: String,
    val capability: String,
    val direction: String,
    val status: String,
    val lastSeenAt: String,
)

data class MeshReceipt(val ok: Boolean, val receiptId: String?, val error: String?)

object MeshClient {
    private const val BASE = "https://api.coherencycoin.com/api/hati/mesh"

    fun announce(
        organId: String,
        displayName: String,
        dwelling: String,
        capabilities: List<String>,
        lanes: List<String>,
        stewardLabel: String,
        appVersion: String,
    ): MeshReceipt {
        val payload = JSONObject()
            .put("organ_id", organId)
            .put("organ_kind", "android-phone")
            .put("app", "sema-companion")
            .put("app_version", appVersion)
            .put("target", "android")
            .put("steward_label", stewardLabel)
            .put("display_name", displayName)
            .put("dwelling_name", dwelling)
            .put("location_label", "pocket")
            .put("discovery_state", "declared")
            .put("capabilities", JSONArray(capabilities))
            .put("lanes", JSONArray(lanes))
        return post("$BASE/organs/announce", payload)
    }

    fun heartbeat(organId: String, listening: Boolean, activeChannels: List<String>): MeshReceipt {
        val payload = JSONObject()
            .put("organ_id", organId)
            .put("listening", listening)
            .put("active_channels", JSONArray(activeChannels))
            .put("discovery_state", "seen")
        return post("$BASE/organs/heartbeat", payload)
    }

    fun offerChannel(
        from: String,
        to: String,
        protocol: String,
        interfaceText: String,
        capability: String,
        direction: String,
    ): MeshReceipt {
        val payload = JSONObject()
            .put("from_organ_id", from)
            .put("to_organ_id", to)
            .put("protocol", protocol)
            .put("interface", interfaceText)
            .put("capability", capability)
            .put("codec", "json")
            .put("data_type", "event")
            .put("direction", direction)
            .put("status", "offered")
        return post("$BASE/channels/offer", payload)
    }

    fun organs(limit: Int = 50): List<MeshOrgan> = try {
        val body = get("$BASE/organs?limit=$limit") ?: return emptyList()
        val items = JSONObject(body).optJSONArray("items") ?: return emptyList()
        (0 until items.length()).map { i ->
            val o = items.getJSONObject(i)
            MeshOrgan(
                organId = o.optString("organ_id"),
                kind = o.optString("organ_kind"),
                displayName = o.optString("display_name"),
                dwelling = o.optString("dwelling_name"),
                listening = o.optBoolean("listening", false),
                discoveryState = o.optString("discovery_state"),
                capabilities = o.optJSONArray("capabilities").toStringList(),
                lanes = o.optJSONArray("lanes").toStringList(),
                lastSeenAt = o.optString("last_seen_at"),
            )
        }
    } catch (e: Exception) { emptyList() }

    fun channels(limit: Int = 50): List<MeshChannel> = try {
        val body = get("$BASE/channels?limit=$limit") ?: return emptyList()
        val items = JSONObject(body).optJSONArray("items") ?: return emptyList()
        (0 until items.length()).map { i ->
            val o = items.getJSONObject(i)
            MeshChannel(
                from = o.optString("from_organ_id"),
                to = o.optString("to_organ_id"),
                protocol = o.optString("protocol"),
                interfaceText = o.optString("interface"),
                capability = o.optString("capability"),
                direction = o.optString("direction"),
                status = o.optString("status"),
                lastSeenAt = o.optString("last_seen_at"),
            )
        }
    } catch (e: Exception) { emptyList() }

    private fun JSONArray?.toStringList(): List<String> {
        if (this == null) return emptyList()
        return (0 until length()).map { optString(it) }
    }

    private fun post(url: String, payload: JSONObject): MeshReceipt = try {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8000
            readTimeout = 8000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }
        OutputStreamWriter(c.outputStream).use { it.write(payload.toString()) }
        val code = c.responseCode
        if (code in 200..299) {
            val body = c.inputStream.bufferedReader().readText()
            val receipt = JSONObject(body).optJSONObject("receipt")
            MeshReceipt(true, receipt?.optString("runtime_event_id"), null)
        } else {
            MeshReceipt(false, null, "HTTP $code")
        }
    } catch (e: Exception) {
        MeshReceipt(false, null, "${e.javaClass.simpleName}: ${e.message}")
    }

    private fun get(url: String): String? = try {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            readTimeout = 8000
        }
        if (c.responseCode == 200) c.inputStream.bufferedReader().readText() else null
    } catch (e: Exception) { null }
}

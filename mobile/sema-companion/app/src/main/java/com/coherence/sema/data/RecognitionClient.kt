package com.coherence.sema.data

// RecognitionClient — the phone's reach into the recognition body. The Mac runs the profile
// engines and the sample stores; it announces its LAN door on the mesh (learning/recognition-
// endpoint). This client finds that door by reading the field (never a hardcoded address —
// an organ is not its address), then does what the mac rooms do: read the board, hear/see a
// pooled sample, assign / unassign / rename — full parity, driven from the pocket.

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class RecogPerson(val person: String, val n: Int)
data class RecogSample(val id: String, val nearestScore: Double?, val source: String?)
data class RecogDomain(val known: List<RecogPerson>, val pool: List<RecogSample>)
data class RecogBoard(val speakers: RecogDomain, val faces: RecogDomain)

object RecognitionClient {

    // the URL the Mac recognition-server posted to the mesh, or null if not on the field
    fun endpoint(channels: List<MeshChannel>): String? =
        channels.firstOrNull { it.interfaceText == "learning/recognition-endpoint" }
            ?.capability?.takeIf { it.startsWith("http") }

    fun voiceUrl(base: String, id: String) = "$base/voice/$id.wav"
    fun faceUrl(base: String, id: String) = "$base/face/$id.jpg"

    fun board(base: String): RecogBoard? {
        return try {
            val text = get("$base/board") ?: return null
            parse(JSONObject(text))
        } catch (e: Exception) { null }
    }

    fun assign(base: String, domain: String, id: String, person: String): RecogBoard? =
        postBoard("$base/assign", JSONObject().put("domain", domain).put("id", id).put("person", person))

    fun unassign(base: String, domain: String, id: String): RecogBoard? =
        postBoard("$base/unassign", JSONObject().put("domain", domain).put("id", id))

    fun rename(base: String, domain: String, old: String, new: String): RecogBoard? =
        postBoard("$base/rename", JSONObject().put("domain", domain).put("old", old).put("new", new))

    fun release(base: String, domain: String, person: String): RecogBoard? =
        postBoard("$base/release", JSONObject().put("domain", domain).put("person", person))

    // ── internals ─────────────────────────────────────────────────────────
    private fun parse(o: JSONObject): RecogBoard =
        RecogBoard(domain(o.optJSONObject("speakers")), domain(o.optJSONObject("faces")))

    private fun domain(o: JSONObject?): RecogDomain {
        if (o == null) return RecogDomain(emptyList(), emptyList())
        val known = ArrayList<RecogPerson>()
        o.optJSONArray("known")?.let { for (i in 0 until it.length()) {
            val p = it.getJSONObject(i); known.add(RecogPerson(p.optString("person"), p.optInt("n")))
        } }
        val pool = ArrayList<RecogSample>()
        o.optJSONArray("pool")?.let { for (i in 0 until it.length()) {
            val p = it.getJSONObject(i)
            pool.add(RecogSample(p.optString("id"),
                if (p.isNull("nearest_score")) null else p.optDouble("nearest_score"),
                p.optString("source", null)))
        } }
        return RecogDomain(known, pool)
    }

    private fun get(url: String): String? = try {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"; connectTimeout = 5000; readTimeout = 8000
        }
        if (c.responseCode in 200..299) c.inputStream.bufferedReader().readText() else null
    } catch (e: Exception) { null }

    private fun postBoard(url: String, payload: JSONObject): RecogBoard? = try {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"; doOutput = true; connectTimeout = 5000; readTimeout = 15000
            setRequestProperty("Content-Type", "application/json")
        }
        c.outputStream.use { it.write(payload.toString().toByteArray()) }
        if (c.responseCode in 200..299) parse(JSONObject(c.inputStream.bufferedReader().readText())) else null
    } catch (e: Exception) { null }
}

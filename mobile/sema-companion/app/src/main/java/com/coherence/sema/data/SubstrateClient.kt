package com.coherence.sema.data

// The public substrate door — grounded, attributed reads from the network's own body.
// A miss is a miss; the client never invents a hit.

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

data class GroundedCell(val slug: String, val nodeId: String)

object SubstrateClient {
    private const val BASE = "https://api.coherencycoin.com/api/substrate"

    fun concept(slug: String): GroundedCell? = try {
        val url = URL("$BASE/cell/concept/${URLEncoder.encode(slug, "UTF-8")}")
        val c = (url.openConnection() as HttpURLConnection).apply {
            connectTimeout = 6000
            readTimeout = 6000
        }
        if (c.responseCode == 200) {
            val o = JSONObject(c.inputStream.bufferedReader().readText())
            val bp = o.optJSONObject("blueprint")
            val node = if (bp != null)
                "@${bp.opt("package")}.${bp.opt("level")}.${bp.opt("type")}.${bp.opt("instance")}"
            else ""
            GroundedCell(slug, node)
        } else null
    } catch (e: Exception) { null }
}

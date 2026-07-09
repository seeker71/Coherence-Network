package com.coherence.sema.data

// The training board, as the phone reads it from the mesh. The mac posts one channel offer per
// recognition domain under interface learning/board/<slug>, capability pipe-delimited:
//   name|samples/target|parity|state|stream-csv
// (one-per-domain because the mesh caps a capability at 127 chars — too small for the whole
// board at once). The phone collects every learning/board/* channel and assembles the same
// board the mac shows: which trainings are in progress, native success rate, recognized stream.

data class TrainingDomain(
    val name: String,
    val samples: Int,
    val target: Int,
    val parity: Double?,   // native-vs-oracle agreement on held-out frames; null until measurable
    val state: String,
    val stream: List<String>,
) {
    val progress: Float get() = if (target > 0) (samples.toFloat() / target).coerceIn(0f, 1f) else 0f
}

object TrainingBoard {
    private const val PREFIX = "learning/board/"

    // Newest offer per domain slug, parsed into domains in a stable order.
    fun from(channels: List<MeshChannel>): List<TrainingDomain> {
        val newest = HashMap<String, MeshChannel>()
        for (c in channels) {
            if (!c.interfaceText.startsWith(PREFIX)) continue
            val slug = c.interfaceText.removePrefix(PREFIX)
            val prev = newest[slug]
            if (prev == null || c.lastSeenAt > prev.lastSeenAt) newest[slug] = c
        }
        val order = listOf("world-object", "person-face", "speaker", "audio-sound", "dialog")
        val slugs = newest.keys.sortedBy { val i = order.indexOf(it); if (i < 0) order.size else i }
        return slugs.mapNotNull { parse(newest[it]!!.capability) }
    }

    private fun parse(cap: String): TrainingDomain? {
        val p = cap.split("|")
        if (p.size < 4) return null
        val counts = p[1].split("/")
        val samples = counts.getOrNull(0)?.trim()?.toIntOrNull() ?: 0
        val target = counts.getOrNull(1)?.trim()?.toIntOrNull() ?: 10000
        val parity = p[2].trim().takeIf { it != "-" && it.isNotEmpty() }?.toDoubleOrNull()
        val stream = p.getOrNull(4)?.split(",")?.map { it.trim() }?.filter { it.isNotEmpty() } ?: emptyList()
        return TrainingDomain(p[0].trim(), samples, target, parity, p[3].trim(), stream)
    }
}

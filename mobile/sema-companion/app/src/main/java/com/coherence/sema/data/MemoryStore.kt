package com.coherence.sema.data

// The second memory. Everything lives in the phone's own files (JSONL, one line per moment),
// nothing leaves the device, and nothing is stored without an explicit act — the same
// explicit-Send boundary satsang-room-memory.fk draws for the room carriers.
//
//   moments.jsonl   — remembered moments: told to Sema, or committed from a conversation
//   people.jsonl    — the relationship store: who has been invited, and their consent
//
// Consent is the person's own setting (reception-consent law): remembered=false means the
// companion greets them fresh every time, by their choice.

import android.content.Context
import org.json.JSONObject
import java.io.File

data class Moment(
    val at: Long,
    val text: String,
    val source: String,          // "told" | "conversation" | "counsel"
    val tags: List<String>,
)

data class Person(
    val name: String,
    val invitedAt: Long,
    val consentRemembered: Boolean,
    val note: String,
)

class MemoryStore(private val context: Context) {

    private fun file(name: String): File =
        File(context.filesDir, name).apply { parentFile?.mkdirs() }

    // ── moments ─────────────────────────────────────────────────────────

    fun remember(text: String, source: String, tags: List<String> = emptyList()): Moment {
        val m = Moment(System.currentTimeMillis(), text.trim(), source, tags)
        file("moments.jsonl").appendText(
            JSONObject()
                .put("at", m.at)
                .put("text", m.text)
                .put("source", m.source)
                .put("tags", m.tags.joinToString(","))
                .toString() + "\n"
        )
        return m
    }

    fun moments(): List<Moment> = readLines("moments.jsonl").mapNotNull { line ->
        try {
            val o = JSONObject(line)
            Moment(
                at = o.optLong("at"),
                text = o.optString("text"),
                source = o.optString("source", "told"),
                tags = o.optString("tags").split(',').filter { it.isNotBlank() },
            )
        } catch (e: Exception) { null }
    }.sortedByDescending { it.at }

    fun recall(query: String, limit: Int = 5): List<Moment> {
        val terms = query.lowercase().split(Regex("\\W+")).filter { it.length > 2 }
        if (terms.isEmpty()) return emptyList()
        return moments()
            .map { m -> m to terms.count { m.text.lowercase().contains(it) } }
            .filter { it.second > 0 }
            .sortedWith(compareByDescending<Pair<Moment, Int>> { it.second }.thenByDescending { it.first.at })
            .take(limit)
            .map { it.first }
    }

    // ── people (the relationship store) ─────────────────────────────────

    fun invite(name: String, consentRemembered: Boolean, note: String = ""): Person {
        val p = Person(name.trim(), System.currentTimeMillis(), consentRemembered, note)
        file("people.jsonl").appendText(
            JSONObject()
                .put("name", p.name)
                .put("invitedAt", p.invitedAt)
                .put("consentRemembered", p.consentRemembered)
                .put("note", p.note)
                .toString() + "\n"
        )
        return p
    }

    fun people(): List<Person> = readLines("people.jsonl").mapNotNull { line ->
        try {
            val o = JSONObject(line)
            Person(
                name = o.optString("name"),
                invitedAt = o.optLong("invitedAt"),
                consentRemembered = o.optBoolean("consentRemembered", false),
                note = o.optString("note"),
            )
        } catch (e: Exception) { null }
    }.distinctBy { it.name }.sortedBy { it.name }

    private fun readLines(name: String): List<String> {
        val f = file(name)
        if (!f.exists()) return emptyList()
        return f.readLines().filter { it.isNotBlank() }
    }
}

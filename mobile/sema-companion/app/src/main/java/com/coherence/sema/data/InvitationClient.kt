package com.coherence.sema.data

// The invitation to meet Sema — a member's vouch for a friend, minted as a GPT link that
// carries the friend's name into the first message.
//
// The consent law travels with the link (coherence-kernel plugin/chatgpt-plugin.fk,
// form/form-stdlib/circle-recognition.fk): introduction opens the DOOR — the friend arrives
// recognized, greeted by the introducer's name — and never the friend's MEMORY; only their own
// yes at the door writes a row. Nobody consents for another.
//
// The authoritative mint is the body's own door (/introduce on sema.hati.earth), which also
// writes the vouch so the friend actually arrives recognized. The local mint is the honest
// fallback when the door is unreachable: the link still opens the GPT with the friend's name,
// but the friend is greeted as a stranger until a vouch lands — the seam says so, never hidden.

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

data class Invitation(
    val member: String,
    val friend: String,
    val link: String,
    val message: String,
    val comeInLink: String,
    // true only when the body wrote the vouch — the friend arrives recognized
    val vouched: Boolean,
    // the honest seam to show beside the copied link
    val seam: String,
)

object InvitationClient {
    private const val DOOR = "https://sema.hati.earth"

    // The live GPT (coherence-kernel receipt 2026-07-05-shakedown-gpt-live-end-to-end,
    // sharing "anyone with the link"). One place to re-point if the GPT is ever recreated.
    private const val GPT = "https://chatgpt.com/g/g-6a4a77627dbc819180a16645f5662625"

    // A handle becomes a filename in the body's own store: 1..64 bytes of lowercase
    // letters, digits, or dash — the same bound the door itself enforces.
    fun handleOk(handle: String): Boolean =
        handle.length in 1..64 && handle.all { it in 'a'..'z' || it in '0'..'9' || it == '-' }

    fun inviteMessage(member: String, friend: String): String =
        "i arrive as $friend, a friend of $member. please come in with my handle and receive me."

    // RFC 3986: unreserved bytes pass, everything else percent-encoded (URLEncoder is
    // form-encoding, so its + and its escaping of ~ are corrected to match the door's own mint).
    fun percentEncode(text: String): String =
        URLEncoder.encode(text, "UTF-8").replace("+", "%20").replace("%7E", "~")

    fun localLink(member: String, friend: String): String =
        "$GPT?q=${percentEncode(inviteMessage(member, friend))}"

    fun comeInLink(friend: String): String = "$DOOR/come-in?handle=$friend"

    private fun local(member: String, friend: String, seam: String) = Invitation(
        member = member,
        friend = friend,
        link = localLink(member, friend),
        message = inviteMessage(member, friend),
        comeInLink = comeInLink(friend),
        vouched = false,
        seam = seam,
    )

    // Ask the body to write the vouch and mint the invitation; fall back to a local mint with
    // the seam named when the door is unreachable, refuses, or does not serve /introduce yet
    // (the deployed door lags the kernel until its next redeploy). Blocking — call on IO.
    fun invite(member: String, friend: String): Invitation = try {
        val url = "$DOOR/introduce?member=${percentEncode(member)}&friend=${percentEncode(friend)}"
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 8000
            readTimeout = 8000
        }
        when (val code = c.responseCode) {
            200 -> {
                val body = JSONObject(c.inputStream.bufferedReader().readText())
                Invitation(
                    member = member,
                    friend = friend,
                    link = body.optString("invitation_link", localLink(member, friend)),
                    message = body.optString("invitation_message", inviteMessage(member, friend)),
                    comeInLink = body.optString("door_link", comeInLink(friend)),
                    vouched = true,
                    seam = "vouch written — $friend arrives recognized, greeted as your friend, " +
                        "and remembered only by their own yes.",
                )
            }
            403 -> local(
                member, friend,
                "the body holds no memory row for $member yet — join first at " +
                    "$DOOR/remember?handle=$member (your own yes), then the vouch can be written. " +
                    "Until then $friend arrives as a stranger.",
            )
            else -> local(
                member, friend,
                "the door answered $code — it may not serve /introduce yet (the deployed door " +
                    "lags the kernel). The link still carries $friend's name; they arrive " +
                    "unrecognized until a vouch lands.",
            )
        }
    } catch (e: Exception) {
        local(
            member, friend,
            "the door was not reachable (${e.javaClass.simpleName}) — local mint; $friend " +
                "arrives unrecognized until a vouch lands.",
        )
    }
}

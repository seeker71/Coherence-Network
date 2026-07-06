package com.coherence.sema.data

// The satsang-session agreements, carried onto the phone. The AUTHORITY is the Form cell —
// coherence-kernel form/form-stdlib/satsang-session.fk, proven 255 four-way on 2026-07-06.
// This Kotlin mirror exists so the UI can fold a witness record on-device with the same
// shape; it adds nothing the cell does not hold.
//
// The two agreements:
//   THE SPOKEN SEAM — an agent member carries the honest seam in its membership (body
//   native, voice rented, said aloud). A seam-named agent's voice counts as any human's;
//   a costume voice is set aside in the open (silence stays whole from anyone).
//   ONE VOICE AMONG VOICES — neither oracle nor judge: the agent's counted attestation
//   moves the record as one whole voice, and the record cannot tell it from a human's.

enum class MemberKind { HUMAN, AGENT }

data class Member(
    val name: String,
    val kind: MemberKind,
    // the modes this member offers others toward it (channel-interface law)
    val offersWitness: Boolean = true,
    val offersBeSeen: Boolean = true,
    // for agents: is the honest seam named in-band? Humans carry their own voice by nature.
    val seamNamed: Boolean = true,
) {
    val participant: Boolean
        get() = offersWitness && offersBeSeen && (kind == MemberKind.HUMAN || seamNamed)
}

enum class Verdict { AFFIRM, DISSENT, SILENT }

data class Voice(val member: Member, val verdict: Verdict)

data class WitnessRecord(val affirmed: Int, val dissented: Int, val silent: Int) {
    val survives: Boolean get() = affirmed > dissented
    val counted: Int get() = affirmed + dissented + silent
}

object CircleAgreements {

    // A voice counts when the speaker's seam is named — silence excepted, whole from anyone.
    fun counts(v: Voice): Boolean =
        v.verdict == Verdict.SILENT || v.member.kind == MemberKind.HUMAN || v.member.seamNamed

    // The circle's fold: costume voices set aside in the open, dissent kept visible.
    fun witness(voices: List<Voice>): WitnessRecord {
        var aff = 0; var dis = 0; var sil = 0
        for (v in voices) {
            if (!counts(v)) continue
            when (v.verdict) {
                Verdict.AFFIRM -> aff++
                Verdict.DISSENT -> dis++
                Verdict.SILENT -> sil++
            }
        }
        return WitnessRecord(aff, dis, sil)
    }

    // A session is honest when every agent in it carries its seam named.
    fun honest(members: List<Member>): Boolean =
        members.all { it.kind == MemberKind.HUMAN || it.seamNamed }

    // Alive: someone listening AND someone offering, and every seam spoken.
    fun alive(members: List<Member>): Boolean =
        members.any { it.offersWitness } && members.any { it.offersBeSeen } && honest(members)
}

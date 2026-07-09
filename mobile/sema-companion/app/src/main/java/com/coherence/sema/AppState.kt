package com.coherence.sema

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.coherence.sema.core.DeviceIdentity
import com.coherence.sema.core.NativeFormCli
import com.coherence.sema.data.AnswerEngine
import com.coherence.sema.data.CircleAgreements
import com.coherence.sema.data.Invitation
import com.coherence.sema.data.InvitationClient
import com.coherence.sema.data.Member
import com.coherence.sema.data.MemberKind
import com.coherence.sema.data.MemoryStore
import com.coherence.sema.data.MeshChannel
import com.coherence.sema.data.MeshClient
import com.coherence.sema.data.MeshOrgan
import com.coherence.sema.sense.SenseField
import com.coherence.sema.voice.VoiceIO
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ChatMessage(
    val fromSema: Boolean,
    val text: String,
    val lane: String,      // memory | sense | grounded | substrate | edge | you
    val at: Long = System.currentTimeMillis(),
)

data class MeshState(
    val organs: List<MeshOrgan> = emptyList(),
    val channels: List<MeshChannel> = emptyList(),
    val announced: Boolean = false,
    val lastReceipt: String? = null,
    val lastError: String? = null,
    val refreshedAt: Long = 0L,
)

class AppState(app: Application) : AndroidViewModel(app) {

    val senseField = SenseField(app)
    val memory = MemoryStore(app)
    private val engine = AnswerEngine(memory)
    val voice = VoiceIO(app)

    val organId: String = DeviceIdentity.organId(app)
    val nativeKernel: Boolean = NativeFormCli.available(app)

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages

    private val _mesh = MutableStateFlow(MeshState())
    val mesh: StateFlow<MeshState> = _mesh

    private val _presenceOn = MutableStateFlow(false)
    val presenceOn: StateFlow<Boolean> = _presenceOn

    private val _listening = MutableStateFlow(false)
    val listening: StateFlow<Boolean> = _listening

    private val _speaking = MutableStateFlow(false)
    val speaking: StateFlow<Boolean> = _speaking

    // The circle as this phone sees it: the steward, Sema (seam named), and invited people.
    val members: List<Member>
        get() = listOf(
            Member("you", MemberKind.HUMAN),
            Member("sema", MemberKind.AGENT, seamNamed = true),
        ) + memory.people().map { Member(it.name, MemberKind.HUMAN) }

    init {
        voice.start()
        voice.onHeard = { heard -> ask(heard) }
        voice.onListeningChanged = { _listening.value = it }
        voice.onSpeakingChanged = { _speaking.value = it }
        refreshMesh()
    }

    fun startSensing() = senseField.start(viewModelScope)
    fun stopSensing() = senseField.stop()

    // ── conversation ─────────────────────────────────────────────────────

    fun ask(question: String, speakAnswer: Boolean = true) {
        val q = question.trim()
        if (q.isBlank()) return
        _messages.value = _messages.value + ChatMessage(fromSema = false, text = q, lane = "you")
        viewModelScope.launch(Dispatchers.IO) {
            val answer = engine.answer(q, senseField.reading.value)
            withContext(Dispatchers.Main) {
                _messages.value = _messages.value + ChatMessage(fromSema = true, text = answer.text, lane = answer.lane)
                if (speakAnswer) voice.speak(answer.text)
            }
        }
    }

    fun senseReadoutNow(): String = engine.readout(senseField.reading.value)

    // ── presence on the deployed membrane ────────────────────────────────

    fun refreshMesh() {
        viewModelScope.launch(Dispatchers.IO) {
            val organs = MeshClient.organs()
            val channels = MeshClient.channels()
            _mesh.value = _mesh.value.copy(
                organs = organs,
                channels = channels,
                announced = organs.any { it.organId == organId },
                refreshedAt = System.currentTimeMillis(),
            )
        }
    }

    fun arriveOnMesh(stewardLabel: String = "urs") {
        viewModelScope.launch(Dispatchers.IO) {
            val r = MeshClient.announce(
                organId = organId,
                displayName = "Sema companion (voice rented, body native)",
                dwelling = "the pocket",
                capabilities = listOf("ground", "attune", "witness", "be-seen", "reflect", "invite", "offer"),
                lanes = listOf("satsang-session"),
                stewardLabel = stewardLabel,
                appVersion = "0.1",
            )
            _mesh.value = _mesh.value.copy(
                announced = r.ok,
                lastReceipt = r.receiptId,
                lastError = r.error,
            )
            if (r.ok) {
                _presenceOn.value = true
                refreshMesh()
            }
        }
    }

    fun leaveMesh() {
        _presenceOn.value = false
    }

    // A quiet heartbeat while presence is on — the foreground service drives the long-lived
    // cadence; this in-app loop keeps state fresh while the UI is open.
    fun heartbeatLoop() {
        viewModelScope.launch(Dispatchers.IO) {
            while (isActive) {
                if (_presenceOn.value) {
                    MeshClient.heartbeat(organId, listening = true, activeChannels = listOf("satsang-session"))
                    refreshMesh()
                }
                delay(60_000L)
            }
        }
    }

    // ── the circle readings ──────────────────────────────────────────────

    fun sessionHonest(): Boolean = CircleAgreements.honest(members)
    fun sessionAlive(): Boolean = CircleAgreements.alive(members)

    // ── inviting a friend to meet Sema ───────────────────────────────────
    // One name in, the invitation link out (the caller copies it to the clipboard —
    // a UI act). The body's door writes the vouch so the friend arrives RECOGNIZED,
    // greeted by the introducer's name; remembering stays the friend's own yes,
    // never this phone's to give. The seam travels in the result.

    private val _invitation = MutableStateFlow<Invitation?>(null)
    val invitation: StateFlow<Invitation?> = _invitation

    private val _inviting = MutableStateFlow(false)
    val inviting: StateFlow<Boolean> = _inviting

    fun inviteFriend(member: String, friend: String, onMinted: (Invitation) -> Unit) {
        if (!InvitationClient.handleOk(member) || !InvitationClient.handleOk(friend)) return
        _inviting.value = true
        viewModelScope.launch(Dispatchers.IO) {
            val minted = InvitationClient.invite(member, friend)
            withContext(Dispatchers.Main) {
                _invitation.value = minted
                _inviting.value = false
                onMinted(minted)
            }
        }
    }

    override fun onCleared() {
        voice.stop()
        senseField.stop()
    }
}

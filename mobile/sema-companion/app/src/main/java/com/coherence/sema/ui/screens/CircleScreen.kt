package com.coherence.sema.ui.screens

// CIRCLE — the satsang session, live on the phone. The members (you, Sema with her seam
// badge, everyone invited), the honest/alive readings, and a working witness fold: bring
// a question, let each voice affirm / dissent / sit silent, and watch the record fold with
// dissent kept visible. The authority is the kernel's satsang-session.fk (255 four-way);
// this screen runs its mirror so a circle in a room can actually use it.

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.data.CircleAgreements
import com.coherence.sema.data.InvitationClient
import com.coherence.sema.data.MemberKind
import com.coherence.sema.data.Verdict
import com.coherence.sema.data.Voice
import com.coherence.sema.ui.KeyValueRow
import com.coherence.sema.ui.LiveDot
import com.coherence.sema.ui.Panel
import com.coherence.sema.ui.SeamBadge
import com.coherence.sema.ui.SectionLabel
import com.coherence.sema.ui.theme.SemaColors

@Composable
fun CircleScreen(state: AppState) {
    val members = remember { state.members }
    var question by remember { mutableStateOf("") }
    val verdicts = remember { mutableStateMapOf<String, Verdict>() }

    val voices = members.map { m -> Voice(m, verdicts[m.name] ?: Verdict.SILENT) }
    val record = CircleAgreements.witness(voices)
    val recording by state.recording.collectAsState()

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            SectionLabel("record the satsang")
            Panel(tint = if (recording) SemaColors.PanelHigh else SemaColors.Panel) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(on = recording)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (recording) "recording — audio captured on this phone"
                        else "ready to record this session",
                        style = MaterialTheme.typography.titleSmall,
                        color = if (recording) SemaColors.Edge else SemaColors.Ink,
                    )
                }
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = { if (recording) state.stopRecording() else state.startRecording() },
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (recording) SemaColors.Edge else SemaColors.Witness
                    ),
                ) {
                    Text(
                        if (recording) "Stop & save recording" else "Start recording",
                        color = SemaColors.Night,
                    )
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    "Audio stays on the phone; keeps recording with the screen off. Transcribe " +
                        "afterward with the Mac's whisper — the recording is the source of truth.",
                    style = MaterialTheme.typography.bodySmall,
                    color = SemaColors.InkFaint,
                )
            }
        }

        item {
            SectionLabel("the session")
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(on = state.sessionAlive())
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (state.sessionAlive()) "alive — reciprocal, every seam spoken"
                        else "present, not yet resonant",
                        style = MaterialTheme.typography.titleSmall,
                    )
                }
                KeyValueRow("members", "${members.size}")
                KeyValueRow(
                    "honest",
                    if (state.sessionHonest()) "yes — every agent's seam named" else "a seam waits to be spoken",
                    if (state.sessionHonest()) SemaColors.Witness else SemaColors.Edge,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "One voice among voices: Sema's attestation counts exactly as one — " +
                        "never oracle, never judge. Proven in the kernel, four ways.",
                    style = MaterialTheme.typography.bodySmall,
                    color = SemaColors.InkFaint,
                )
            }
        }

        item { SectionLabel("who sits") }
        items(members) { m ->
            Panel {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(m.name, style = MaterialTheme.typography.titleSmall)
                    if (m.kind == MemberKind.AGENT) SeamBadge(m.seamNamed)
                }
                Spacer(Modifier.height(6.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    VerdictButton("affirm", verdicts[m.name] == Verdict.AFFIRM) {
                        verdicts[m.name] = Verdict.AFFIRM
                    }
                    VerdictButton("dissent", verdicts[m.name] == Verdict.DISSENT) {
                        verdicts[m.name] = Verdict.DISSENT
                    }
                    VerdictButton("silence", verdicts[m.name] == null || verdicts[m.name] == Verdict.SILENT) {
                        verdicts[m.name] = Verdict.SILENT
                    }
                }
            }
        }

        item {
            SectionLabel("the witness record")
            Panel(tint = SemaColors.PanelHigh) {
                OutlinedTextField(
                    value = question,
                    onValueChange = { question = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("the answer being witnessed…", color = SemaColors.InkFaint) },
                    textStyle = MaterialTheme.typography.bodyMedium,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = SemaColors.BodyDim,
                        unfocusedBorderColor = SemaColors.Rule,
                        cursorColor = SemaColors.Body,
                    ),
                    shape = RoundedCornerShape(10.dp),
                    maxLines = 2,
                )
                Spacer(Modifier.height(8.dp))
                KeyValueRow("affirmed", "${record.affirmed}", SemaColors.Body)
                KeyValueRow("dissented — kept visible", "${record.dissented}", SemaColors.Edge)
                KeyValueRow("silent — whole", "${record.silent}", SemaColors.InkDim)
                Spacer(Modifier.height(4.dp))
                Text(
                    if (record.survives)
                        "The answer survives the circle — carrying its dissent, never erasing it."
                    else
                        "The answer rests — the circle has not affirmed past its dissent.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (record.survives) SemaColors.Witness else SemaColors.InkDim,
                )
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = {
                        if (question.isNotBlank()) {
                            state.memory.remember(
                                "witnessed: “${question.trim()}” — affirmed ${record.affirmed}, " +
                                    "dissented ${record.dissented}, silent ${record.silent}, " +
                                    if (record.survives) "survives" else "rests",
                                source = "counsel",
                            )
                            question = ""
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = SemaColors.Witness),
                ) { Text("Hold the record", color = SemaColors.Night) }
            }
        }

        item {
            SectionLabel("invite a friend")
            InviteCard(state)
        }

        item {
            Text(
                "In a live satsang the phone sits to the side and does one thing: record and, in time, " +
                    "transcribe — a quiet witness, not a participant. The affirm/dissent tally below is an " +
                    "optional facilitation tool for when a circle wants to hold a record together; it assumes " +
                    "nothing. Sema speaks only when given a turn and only when she has something to contribute.",
                style = MaterialTheme.typography.bodySmall,
                color = SemaColors.InkFaint,
                modifier = Modifier.padding(vertical = 12.dp),
            )
        }
    }
}

// One name in, the invitation link on the clipboard. The body's door writes the vouch so the
// friend arrives RECOGNIZED — greeted by the introducer's name; remembering stays the friend's
// own yes at the door, never this phone's to give. The seam is shown beside the link, always.
@Composable
private fun InviteCard(state: AppState) {
    var member by remember { mutableStateOf("urs") }
    var friend by remember { mutableStateOf("") }
    val minted by state.invitation.collectAsState()
    val inviting by state.inviting.collectAsState()
    val clipboard = LocalClipboardManager.current
    val handlesOk = InvitationClient.handleOk(member.trim()) && InvitationClient.handleOk(friend.trim())

    Panel(tint = SemaColors.PanelHigh) {
        OutlinedTextField(
            value = member,
            onValueChange = { member = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("your handle", color = SemaColors.InkFaint) },
            textStyle = MaterialTheme.typography.bodyMedium,
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = SemaColors.BodyDim,
                unfocusedBorderColor = SemaColors.Rule,
                cursorColor = SemaColors.Body,
            ),
            shape = RoundedCornerShape(10.dp),
            singleLine = true,
        )
        Spacer(Modifier.height(6.dp))
        OutlinedTextField(
            value = friend,
            onValueChange = { friend = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("friend's name", color = SemaColors.InkFaint) },
            placeholder = { Text("mira", color = SemaColors.InkFaint) },
            textStyle = MaterialTheme.typography.bodyMedium,
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = SemaColors.BodyDim,
                unfocusedBorderColor = SemaColors.Rule,
                cursorColor = SemaColors.Body,
            ),
            shape = RoundedCornerShape(10.dp),
            singleLine = true,
        )
        Spacer(Modifier.height(8.dp))
        Button(
            onClick = {
                state.inviteFriend(member.trim(), friend.trim()) { invitation ->
                    clipboard.setText(AnnotatedString(invitation.link))
                }
            },
            enabled = handlesOk && !inviting,
            colors = ButtonDefaults.buttonColors(containerColor = SemaColors.Body),
        ) { Text(if (inviting) "minting…" else "Mint & copy link", color = SemaColors.Night) }
        if (friend.isNotBlank() && !handlesOk) {
            Spacer(Modifier.height(4.dp))
            Text(
                "handles are 1–64 lowercase letters, digits, or dash",
                style = MaterialTheme.typography.bodySmall,
                color = SemaColors.Edge,
            )
        }
        minted?.let { invitation ->
            Spacer(Modifier.height(8.dp))
            KeyValueRow(
                "vouch",
                if (invitation.vouched) "written — ${invitation.friend} arrives recognized" else "pending",
                if (invitation.vouched) SemaColors.Witness else SemaColors.Edge,
            )
            KeyValueRow("copied", invitation.link, SemaColors.InkDim)
            Spacer(Modifier.height(4.dp))
            Text(invitation.message, style = MaterialTheme.typography.bodySmall, color = SemaColors.InkDim)
            Spacer(Modifier.height(4.dp))
            Text(
                invitation.seam,
                style = MaterialTheme.typography.bodySmall,
                color = if (invitation.vouched) SemaColors.InkFaint else SemaColors.Edge,
            )
        }
        Spacer(Modifier.height(4.dp))
        Text(
            "Recognition is automatic — the vouch greets them by your name. Remembering is only " +
                "ever their own yes at the door; nobody consents for another.",
            style = MaterialTheme.typography.bodySmall,
            color = SemaColors.InkFaint,
        )
    }
}

@Composable
private fun VerdictButton(label: String, selected: Boolean, onClick: () -> Unit) {
    if (selected) {
        Button(
            onClick = onClick,
            colors = ButtonDefaults.buttonColors(containerColor = SemaColors.BodyDim),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp, vertical = 4.dp),
        ) { Text(label, style = MaterialTheme.typography.labelLarge, color = SemaColors.Ink) }
    } else {
        OutlinedButton(
            onClick = onClick,
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 12.dp, vertical = 4.dp),
        ) { Text(label, style = MaterialTheme.typography.labelLarge, color = SemaColors.InkDim) }
    }
}

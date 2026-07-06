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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.data.CircleAgreements
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

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
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
            Text(
                "The circle witnesses how an answer is offered — who affirms, who dissents, who " +
                    "sits silent. It never claims to pierce the one who offered it.",
                style = MaterialTheme.typography.bodySmall,
                color = SemaColors.InkFaint,
                modifier = Modifier.padding(vertical = 12.dp),
            )
        }
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

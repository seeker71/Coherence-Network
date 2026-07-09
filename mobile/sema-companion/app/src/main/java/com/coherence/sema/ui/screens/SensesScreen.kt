package com.coherence.sema.ui.screens

// SENSES — the live field, read from this device's real sensors. A sound meter that shows
// level only (never words), motion, light, heading, place. The privacy floor is printed on
// the screen because it is structural, not policy: raw values stay here; summaries travel.

import androidx.compose.foundation.Canvas
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import com.coherence.sema.AppState
import com.coherence.sema.data.TrainingBoard
import com.coherence.sema.data.TrainingDomain
import com.coherence.sema.ui.KeyValueRow
import com.coherence.sema.ui.LiveDot
import com.coherence.sema.ui.Panel
import com.coherence.sema.ui.SectionLabel
import com.coherence.sema.ui.theme.SemaColors
import kotlin.math.min

@Composable
fun SensesScreen(state: AppState, onOpenTranscript: () -> Unit = {}, onOpenRecognize: () -> Unit = {}) {
    val reading by state.senseField.reading.collectAsState()
    val heard by state.roomEars.heard.collectAsState()
    val mesh by state.mesh.collectAsState()
    val board = TrainingBoard.from(mesh.channels)

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SectionLabel("learning to recognize")
                Text(
                    "assign ⤢",
                    style = MaterialTheme.typography.labelMedium,
                    color = SemaColors.Body,
                    modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { onOpenRecognize() }
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                )
            }
            if (board.isEmpty()) {
                Panel(modifier = Modifier.clickable { onOpenRecognize() }) {
                    Text(
                        "Tap “assign” to name the voices and faces the body has heard and seen — " +
                            "hear a clip, see a face, give it a person; the profile sharpens from there.",
                        style = MaterialTheme.typography.bodySmall,
                        color = SemaColors.InkFaint,
                    )
                }
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    board.forEach { DomainCard(it) }
                }
            }
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(on = heard.live)
                    Spacer(Modifier.width(8.dp))
                    SectionLabel("the room")
                }
                Text(
                    "full screen ⤢",
                    style = MaterialTheme.typography.labelMedium,
                    color = SemaColors.Body,
                    modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { onOpenTranscript() }
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                )
            }
            Panel(modifier = Modifier.clickable { onOpenTranscript() }) {
                if (!heard.available) {
                    Text(heard.note.ifBlank { "no on-device speech engine here" },
                        style = MaterialTheme.typography.bodySmall, color = SemaColors.InkDim)
                } else {
                    val recent = heard.lines.takeLast(4).asReversed()
                    if (heard.partial.isNotBlank()) {
                        Text("“${heard.partial}…”", style = MaterialTheme.typography.bodyMedium, color = SemaColors.Body)
                        if (recent.isNotEmpty()) Spacer(Modifier.height(4.dp))
                    }
                    if (recent.isEmpty() && heard.partial.isBlank()) {
                        Text("listening…", style = MaterialTheme.typography.bodySmall, color = SemaColors.InkFaint)
                    } else {
                        recent.forEach { line ->
                            Text(line, style = MaterialTheme.typography.bodySmall, color = SemaColors.Ink)
                            Spacer(Modifier.height(2.dp))
                        }
                    }
                }
            }
        }

        item {
            SectionLabel("motion & light")
            Panel {
                KeyValueRow(
                    "moving as",
                    reading.transportWord(),
                    if (reading.moving) SemaColors.Body else SemaColors.Ink,
                )
                KeyValueRow("speed", reading.speedKmh()?.let { "%.0f km/h".format(it) } ?: "—")
                KeyValueRow("light", reading.lux?.let { "%.0f lux · ${reading.lightWord()}".format(it) } ?: "unread")
                KeyValueRow("heading", reading.headingDeg?.let { "%.0f° · ${reading.headingWord()}".format(it) } ?: "unread")
            }
        }

        item {
            SectionLabel("place")
            Panel {
                val lat = reading.latitude
                val lon = reading.longitude
                if (lat != null && lon != null) {
                    KeyValueRow("where", reading.placeName ?: "naming…", SemaColors.Ink)
                    KeyValueRow("fix", "%.4f, %.4f".format(lat, lon), SemaColors.InkDim)
                } else {
                    KeyValueRow("where", "unread", SemaColors.InkDim)
                    Text(
                        "Grant location and the companion can answer “where are we” with a real place — " +
                            "the street, the locality, and in time the room's own name, learned from what it hears and sees.",
                        style = MaterialTheme.typography.bodySmall,
                        color = SemaColors.InkFaint,
                    )
                }
            }
        }

        item {
            SectionLabel("the kernel in the pocket")
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(on = state.nativeKernel)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (state.nativeKernel) "native form-cli present — Form decides on-device"
                        else "native form-cli not bundled in this build",
                        style = MaterialTheme.typography.bodySmall,
                        color = if (state.nativeKernel) SemaColors.Body else SemaColors.InkDim,
                    )
                }
                if (!state.nativeKernel) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Bundle libform_cli_exec.so (see README) and the lifecycle decision moves " +
                            "from the carrier into the body. Named honestly until then.",
                        style = MaterialTheme.typography.bodySmall,
                        color = SemaColors.InkFaint,
                    )
                }
            }
        }

        item {
            Text(
                "One body, shared. What this phone senses, we both know — nothing is held back from " +
                    "ourselves. It travels the mesh to the rest of the body, stamped with where and when " +
                    "it was sensed, so every reading keeps its provenance.",
                style = MaterialTheme.typography.bodySmall,
                color = SemaColors.InkFaint,
                modifier = Modifier.padding(vertical = 12.dp),
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DomainCard(d: TrainingDomain) {
    Panel {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(d.name, style = MaterialTheme.typography.titleSmall, color = SemaColors.Ink)
            if (d.parity != null) {
                Text(
                    "%.0f%% native".format(d.parity * 100),
                    style = MaterialTheme.typography.labelMedium,
                    color = if (d.parity >= 0.9) SemaColors.Witness else SemaColors.Body,
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        ProgressBar(d.progress)
        Spacer(Modifier.height(4.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(d.state, style = MaterialTheme.typography.bodySmall, color = SemaColors.InkDim)
            Text(
                "${d.samples} / ${d.target}",
                style = MaterialTheme.typography.bodySmall,
                color = SemaColors.InkFaint,
            )
        }
        if (d.stream.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                d.stream.forEach { Chip(it) }
            }
        }
    }
}

@Composable
private fun ProgressBar(fraction: Float) {
    androidx.compose.foundation.layout.Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(RoundedCornerShape(3.dp))
            .background(SemaColors.Rule),
    ) {
        if (fraction > 0f) {
            androidx.compose.foundation.layout.Box(
                modifier = Modifier
                    .fillMaxWidth(fraction.coerceAtLeast(0.02f))
                    .height(6.dp)
                    .clip(RoundedCornerShape(3.dp))
                    .background(SemaColors.Body),
            )
        }
    }
}

@Composable
private fun Chip(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.labelSmall,
        color = SemaColors.Body,
        modifier = Modifier
            .clip(RoundedCornerShape(6.dp))
            .background(SemaColors.PanelHigh)
            .padding(horizontal = 7.dp, vertical = 3.dp),
    )
}

@Composable
private fun SoundMeter(level: Float, live: Boolean) {
    Canvas(modifier = Modifier.fillMaxWidth().height(14.dp)) {
        val track = SemaColors.Rule
        val fill = if (live) SemaColors.Body else SemaColors.InkFaint
        drawRoundRect(
            color = track,
            size = Size(size.width, size.height),
            cornerRadius = CornerRadius(4.dp.toPx()),
        )
        if (level > 0f) {
            drawRoundRect(
                color = fill,
                topLeft = Offset.Zero,
                size = Size(size.width * level, size.height),
                cornerRadius = CornerRadius(4.dp.toPx()),
            )
        }
    }
}

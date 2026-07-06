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
import com.coherence.sema.AppState
import com.coherence.sema.ui.KeyValueRow
import com.coherence.sema.ui.LiveDot
import com.coherence.sema.ui.Panel
import com.coherence.sema.ui.SectionLabel
import com.coherence.sema.ui.theme.SemaColors
import kotlin.math.min

@Composable
fun SensesScreen(state: AppState) {
    val reading by state.senseField.reading.collectAsState()

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            SectionLabel("the room")
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(on = reading.micLive)
                    Spacer(Modifier.width(8.dp))
                    Text("sound — level only, never words", style = MaterialTheme.typography.titleSmall)
                }
                Spacer(Modifier.height(8.dp))
                SoundMeter(rms = reading.soundRms, live = reading.micLive)
                Spacer(Modifier.height(4.dp))
                KeyValueRow("reads as", reading.soundWord())
            }
        }

        item {
            SectionLabel("motion & light")
            Panel {
                KeyValueRow(
                    "motion",
                    if (reading.moving) "moving" else "still",
                    if (reading.moving) SemaColors.Body else SemaColors.Ink,
                )
                KeyValueRow("accel beyond gravity", "%.2f m/s²".format(reading.accelMagnitude))
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
                    KeyValueRow("fix", "%.4f, %.4f".format(lat, lon))
                    KeyValueRow("held", "on device — shared only as place-words, on your word")
                } else {
                    KeyValueRow("fix", "unread", SemaColors.InkDim)
                    Text(
                        "Grant location and the companion can answer “where are we” with a real place.",
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
                "Raw sensor values never leave this phone. What travels — when you turn presence on — " +
                    "is level and presence summaries, stamped with provenance. Structural, not policy.",
                style = MaterialTheme.typography.bodySmall,
                color = SemaColors.InkFaint,
                modifier = Modifier.padding(vertical = 12.dp),
            )
        }
    }
}

@Composable
private fun SoundMeter(rms: Int, live: Boolean) {
    val level = min(rms / 8000f, 1f)
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

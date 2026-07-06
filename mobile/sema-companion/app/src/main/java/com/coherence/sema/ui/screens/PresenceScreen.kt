package com.coherence.sema.ui.screens

// PRESENCE — the mesh field. Who is present on the deployed membrane, this phone's own
// arrival (announce receipt visible — trust as something checkable), and every channel
// with its honest interface text.

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.ui.KeyValueRow
import com.coherence.sema.ui.LiveDot
import com.coherence.sema.ui.Panel
import com.coherence.sema.ui.SectionLabel
import com.coherence.sema.ui.theme.SemaColors

@Composable
fun PresenceScreen(state: AppState) {
    val mesh by state.mesh.collectAsState()
    val presenceOn by state.presenceOn.collectAsState()

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        item {
            SectionLabel("this phone")
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(on = mesh.announced)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (mesh.announced) "present on the mesh" else "not yet arrived",
                        style = MaterialTheme.typography.titleSmall,
                    )
                }
                Spacer(Modifier.height(6.dp))
                KeyValueRow("organ", state.organId)
                KeyValueRow("lane", "satsang-session")
                KeyValueRow("seam", "voice rented · body native", SemaColors.Witness)
                mesh.lastReceipt?.let { KeyValueRow("receipt", it, SemaColors.Witness) }
                mesh.lastError?.let { KeyValueRow("edge", it, SemaColors.Edge) }
                Spacer(Modifier.height(8.dp))
                Row {
                    if (!presenceOn) {
                        Button(
                            onClick = { state.arriveOnMesh() },
                            colors = ButtonDefaults.buttonColors(containerColor = SemaColors.Body),
                        ) { Text("Arrive", color = SemaColors.Night) }
                    } else {
                        OutlinedButton(onClick = { state.leaveMesh() }) { Text("Rest") }
                    }
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(onClick = { state.refreshMesh() }) { Text("Sense the field") }
                }
            }
        }

        item { SectionLabel("presences witnessed (${mesh.organs.size})") }
        items(mesh.organs) { organ ->
            Panel {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    LiveDot(on = organ.listening)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        organ.displayName.ifBlank { organ.organId },
                        style = MaterialTheme.typography.titleSmall,
                    )
                }
                KeyValueRow("dwelling", organ.dwelling.ifBlank { "—" })
                KeyValueRow("state", organ.discoveryState)
                if (organ.capabilities.isNotEmpty()) {
                    KeyValueRow("offers", organ.capabilities.joinToString(" · "))
                }
                KeyValueRow("last seen", organ.lastSeenAt.take(19).replace('T', ' '))
            }
        }

        item { SectionLabel("channels (${mesh.channels.size})") }
        items(mesh.channels) { ch ->
            Panel {
                Text(
                    "${ch.from} → ${ch.to}",
                    style = MaterialTheme.typography.bodySmall,
                    color = SemaColors.Ink,
                )
                KeyValueRow("protocol", ch.protocol)
                KeyValueRow("status", ch.status, if (ch.status == "open") SemaColors.Body else SemaColors.InkDim)
                if (ch.interfaceText.isNotBlank()) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        ch.interfaceText,
                        style = MaterialTheme.typography.bodySmall,
                        color = SemaColors.InkDim,
                    )
                }
            }
        }

        item { Spacer(Modifier.height(20.dp)) }
    }
}

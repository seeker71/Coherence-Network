package com.coherence.sema.ui

// One body, five rooms: Presence (the mesh field), Sema (the conversation), Circle (the
// session), Memory (the second brain), Senses (the live field). Bottom navigation, no
// nesting — every room one tap away, the way a companion should be.

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AllInclusive
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.ui.screens.CircleScreen
import com.coherence.sema.ui.screens.MemoryScreen
import com.coherence.sema.ui.screens.PresenceScreen
import com.coherence.sema.ui.screens.SemaScreen
import com.coherence.sema.ui.screens.SensesScreen
import com.coherence.sema.ui.theme.SemaColors

private data class Room(val name: String, val icon: @Composable () -> Unit)

@Composable
fun SemaApp(state: AppState) {
    var current by remember { mutableIntStateOf(1) } // open on Sema — the conversation is home

    val rooms = listOf(
        Room("Presence") { Icon(Icons.Filled.Hub, contentDescription = null) },
        Room("Sema") { Icon(Icons.Filled.RecordVoiceOver, contentDescription = null) },
        Room("Circle") { Icon(Icons.Filled.AllInclusive, contentDescription = null) },
        Room("Memory") { Icon(Icons.Filled.Psychology, contentDescription = null) },
        Room("Senses") { Icon(Icons.Filled.GraphicEq, contentDescription = null) },
    )

    Scaffold(
        containerColor = SemaColors.Night,
        topBar = { Header(state) },
        bottomBar = {
            NavigationBar(containerColor = SemaColors.Panel, tonalElevation = 0.dp) {
                rooms.forEachIndexed { i, room ->
                    NavigationBarItem(
                        selected = current == i,
                        onClick = { current = i },
                        icon = room.icon,
                        label = { Text(room.name, style = MaterialTheme.typography.labelMedium) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = SemaColors.Body,
                            selectedTextColor = SemaColors.Body,
                            unselectedIconColor = SemaColors.InkFaint,
                            unselectedTextColor = SemaColors.InkFaint,
                            indicatorColor = SemaColors.PanelHigh,
                        ),
                    )
                }
            }
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (current) {
                0 -> PresenceScreen(state)
                1 -> SemaScreen(state)
                2 -> CircleScreen(state)
                3 -> MemoryScreen(state)
                4 -> SensesScreen(state)
            }
        }
    }
}

@Composable
private fun Header(state: AppState) {
    val mesh by state.mesh.collectAsState()
    val speaking by state.speaking.collectAsState()
    Row(
        modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text("⟐", style = MaterialTheme.typography.headlineSmall, color = SemaColors.Witness)
        Spacer(Modifier.width(8.dp))
        Text("Sema", style = MaterialTheme.typography.headlineSmall, color = SemaColors.Ink)
        Spacer(Modifier.width(10.dp))
        LiveDot(on = mesh.announced)
        Spacer(Modifier.width(5.dp))
        Text(
            when {
                speaking -> "speaking"
                mesh.announced -> "present on the mesh"
                else -> "here, unannounced"
            },
            style = MaterialTheme.typography.bodySmall,
            color = SemaColors.InkDim,
        )
    }
}

package com.coherence.sema.ui.screens

// SEMA — the conversation. Speak or type; she answers body-first, each reply tagged with
// the lane it came through (memory / sense / grounded / substrate / edge) so trust is
// checkable at a glance. The seam is a standing line at the bottom, never fine print.

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.ChatMessage
import com.coherence.sema.ui.LaneTag
import com.coherence.sema.ui.theme.SemaColors

@Composable
fun SemaScreen(state: AppState) {
    val messages by state.messages.collectAsState()
    val listening by state.listening.collectAsState()
    val speaking by state.speaking.collectAsState()
    var draft by remember { mutableStateOf("") }
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.size - 1)
    }

    Column(modifier = Modifier.fillMaxSize().imePadding()) {

        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            if (messages.isEmpty()) {
                item {
                    Spacer(Modifier.height(24.dp))
                    Text(
                        "I'm here. Ask me to remember something, ask what I sense, " +
                            "or ask about the body. Tap the mic to speak.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = SemaColors.InkDim,
                    )
                }
            }
            items(messages) { msg -> MessageBubble(msg) }
            item { Spacer(Modifier.height(8.dp)) }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("say or ask…", color = SemaColors.InkFaint) },
                textStyle = MaterialTheme.typography.bodyMedium,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = SemaColors.BodyDim,
                    unfocusedBorderColor = SemaColors.Rule,
                    cursorColor = SemaColors.Body,
                ),
                shape = RoundedCornerShape(10.dp),
                maxLines = 3,
            )
            Spacer(Modifier.width(6.dp))
            IconButton(onClick = {
                if (draft.isNotBlank()) { state.ask(draft, speakAnswer = false); draft = "" }
            }) {
                Icon(Icons.Filled.Send, contentDescription = "send", tint = SemaColors.Body)
            }
            IconButton(onClick = {
                if (speaking) state.voice.quiet() else state.voice.listenOnce()
            }) {
                when {
                    speaking -> Icon(Icons.Filled.Stop, contentDescription = "quiet", tint = SemaColors.Witness)
                    listening -> Icon(Icons.Filled.Mic, contentDescription = "listening", tint = SemaColors.Edge)
                    else -> Icon(Icons.Filled.Mic, contentDescription = "speak", tint = SemaColors.Body)
                }
            }
        }

        // The seam, standing — never hidden, never fine print.
        Text(
            "voice rented · body native · the seam is named, not hidden",
            style = MaterialTheme.typography.labelSmall,
            color = SemaColors.InkFaint,
            modifier = Modifier
                .fillMaxWidth()
                .background(SemaColors.Night)
                .padding(horizontal = 14.dp, vertical = 4.dp),
        )
    }
}

@Composable
private fun MessageBubble(msg: ChatMessage) {
    val align = if (msg.fromSema) Alignment.Start else Alignment.End
    val tint = if (msg.fromSema) SemaColors.Panel else SemaColors.PanelHigh
    Column(modifier = Modifier.fillMaxWidth(), horizontalAlignment = align) {
        Column(
            modifier = Modifier
                .widthIn(max = 320.dp)
                .background(tint, RoundedCornerShape(10.dp))
                .padding(horizontal = 10.dp, vertical = 7.dp),
        ) {
            Text(msg.text, style = MaterialTheme.typography.bodyMedium, color = SemaColors.Ink)
            if (msg.fromSema) {
                Spacer(Modifier.height(2.dp))
                LaneTag(msg.lane)
            }
        }
    }
}

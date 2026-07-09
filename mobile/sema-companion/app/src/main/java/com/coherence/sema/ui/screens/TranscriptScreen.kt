package com.coherence.sema.ui.screens

// TRANSCRIPT — the room's words, full screen. Just the transcript, large and scrolling, the
// live words forming at the bottom. Turn on translation and each line is also rendered in the
// chosen language (on-device), so the room can be read live in Portuguese for our Brazilian
// member — or any tongue whose model is downloaded.

import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.ui.theme.SemaColors
import com.coherence.sema.voice.LiveTranslator
import com.google.mlkit.nl.translate.TranslateLanguage

private data class Lang(val label: String, val code: String)

private val LANGS = listOf(
    Lang("Português", TranslateLanguage.PORTUGUESE),
    Lang("English", TranslateLanguage.ENGLISH),
    Lang("Indonesia", TranslateLanguage.INDONESIAN),
    Lang("Español", TranslateLanguage.SPANISH),
    Lang("Deutsch", TranslateLanguage.GERMAN),
)

@Composable
fun TranscriptScreen(state: AppState, onClose: () -> Unit) {
    val heard by state.roomEars.heard.collectAsState()
    var translateOn by remember { mutableStateOf(false) }
    var target by remember { mutableStateOf(TranslateLanguage.PORTUGUESE) }
    val translator = remember { LiveTranslator() }
    val translations = remember { mutableStateMapOf<String, String>() }
    val listState = rememberLazyListState()

    DisposableEffect(Unit) { onDispose { translator.close() } }
    LaunchedEffect(target) { translator.setTarget(target); translations.clear() }
    LaunchedEffect(heard.lines.size, translateOn, target) {
        if (translateOn) {
            heard.lines.forEach { line ->
                if (!translations.containsKey(line)) {
                    translations[line] = "…"
                    translator.translate(line) { out -> translations[line] = out }
                }
            }
        }
    }
    LaunchedEffect(heard.lines.size, heard.partial) {
        val n = heard.lines.size + if (heard.partial.isNotBlank()) 1 else 0
        if (n > 0) listState.animateScrollToItem(n - 1)
    }

    Column(modifier = Modifier.fillMaxSize().background(SemaColors.Night)) {
        // top bar — close, live dot, translation toggle
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "✕ close",
                style = MaterialTheme.typography.labelLarge,
                color = SemaColors.InkDim,
                modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { onClose() }.padding(6.dp),
            )
            Spacer(Modifier.width(12.dp))
            com.coherence.sema.ui.LiveDot(on = heard.live)
            Spacer(Modifier.weight(1f))
            Text("translate", style = MaterialTheme.typography.labelMedium, color = SemaColors.InkDim)
            Spacer(Modifier.width(6.dp))
            Switch(
                checked = translateOn,
                onCheckedChange = { translateOn = it },
                colors = SwitchDefaults.colors(checkedTrackColor = SemaColors.BodyDim),
            )
        }

        // language chips (only when translating)
        if (translateOn) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                LANGS.forEach { lang ->
                    val on = target == lang.code
                    Text(
                        lang.label,
                        style = MaterialTheme.typography.labelMedium,
                        color = if (on) SemaColors.Night else SemaColors.Body,
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (on) SemaColors.Body else SemaColors.PanelHigh)
                            .clickable { target = lang.code }
                            .padding(horizontal = 10.dp, vertical = 5.dp),
                    )
                }
            }
        }

        if (!heard.available) {
            Text(
                heard.note.ifBlank { "no on-device speech engine on this device" },
                style = MaterialTheme.typography.bodyLarge,
                color = SemaColors.InkDim,
                modifier = Modifier.padding(24.dp),
            )
            return@Column
        }

        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().padding(horizontal = 18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(heard.lines) { line ->
                Column {
                    Text(line, style = MaterialTheme.typography.titleMedium, color = SemaColors.Ink)
                    if (translateOn) {
                        val tr = translations[line]
                        if (!tr.isNullOrBlank()) {
                            Text(
                                tr,
                                style = MaterialTheme.typography.titleSmall,
                                color = SemaColors.Body,
                                fontStyle = FontStyle.Italic,
                            )
                        }
                    }
                }
            }
            if (heard.partial.isNotBlank()) {
                item {
                    Text(
                        "${heard.partial}…",
                        style = MaterialTheme.typography.titleMedium,
                        color = SemaColors.BodyDim,
                    )
                }
            }
            item { Spacer(Modifier.height(40.dp)) }
        }
    }
}

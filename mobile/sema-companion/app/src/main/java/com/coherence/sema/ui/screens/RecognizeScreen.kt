package com.coherence.sema.ui.screens

// RECOGNIZE — the interactive twin of the Mac's Speakers/Faces rooms, in the pocket. Reads the
// recognition body over the LAN door the Mac announced on the mesh: the people already known
// (voices and faces, with counts) and the pool waiting to be named. HEAR a pooled voice, SEE a
// pooled face, type a name (or tap a known one) to assign; release a person back to the pool to
// correct a mistake. Not a frozen mirror — a working surface.

import android.media.MediaPlayer
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.text.KeyboardActions
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import com.coherence.sema.AppState
import com.coherence.sema.data.RecogBoard
import com.coherence.sema.data.RecogDomain
import com.coherence.sema.data.RecogPerson
import com.coherence.sema.data.RecogSample
import com.coherence.sema.data.RecognitionClient
import com.coherence.sema.ui.LiveDot
import com.coherence.sema.ui.Panel
import com.coherence.sema.ui.SectionLabel
import com.coherence.sema.ui.theme.SemaColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

@Composable
fun RecognizeScreen(state: AppState, onClose: () -> Unit) {
    val mesh by state.mesh.collectAsState()
    val base = remember(mesh.channels) { RecognitionClient.endpoint(mesh.channels) }
    var board by remember { mutableStateOf<RecogBoard?>(null) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        val b = base ?: return
        scope.launch { withContext(Dispatchers.IO) { RecognitionClient.board(b) }?.let { board = it } }
    }
    LaunchedEffect(base) {
        while (base != null) { refresh(); delay(5000) }
    }
    fun act(block: (String) -> RecogBoard?) {
        val b = base ?: return
        scope.launch { val r = withContext(Dispatchers.IO) { block(b) }; if (r != null) board = r }
    }

    Column(modifier = Modifier.fillMaxSize().background(SemaColors.Night)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("✕ close", style = MaterialTheme.typography.labelLarge, color = SemaColors.InkDim,
                modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { onClose() }.padding(6.dp))
            Spacer(Modifier.width(10.dp))
            Text("recognize", style = MaterialTheme.typography.titleMedium, color = SemaColors.Ink)
            Spacer(Modifier.weight(1f))
            LiveDot(on = base != null)
        }

        if (base == null) {
            Text(
                "The recognition body isn't on the field yet. It appears when the Mac's " +
                    "recognition-server is running and has announced its door to the mesh.",
                style = MaterialTheme.typography.bodyMedium, color = SemaColors.InkDim,
                modifier = Modifier.padding(20.dp),
            )
            return@Column
        }
        val b = board
        if (b == null) {
            Text("reaching the recognition body…", style = MaterialTheme.typography.bodyMedium,
                color = SemaColors.InkFaint, modifier = Modifier.padding(20.dp))
            return@Column
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item { KnownRow("voices — known", b.speakers.known, "voice") { act { base -> RecognitionClient.release(base, "voice", it) } } }
            item { SectionLabel("voices — to name (${b.speakers.pool.size})") }
            items(b.speakers.pool, key = { it.id }) { s ->
                VoicePoolItem(base!!, s, b.speakers.known) { person -> act { base -> RecognitionClient.assign(base, "voice", s.id, person) } }
            }
            item { KnownRow("faces — known", b.faces.known, "face") { act { base -> RecognitionClient.release(base, "face", it) } } }
            item { SectionLabel("faces — to name (${b.faces.pool.size})") }
            item {
                LazyVerticalGridBlock(base!!, b.faces.pool, b.faces.known) { id, person -> act { base -> RecognitionClient.assign(base, "face", id, person) } }
            }
            item { Spacer(Modifier.height(30.dp)) }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun KnownRow(label: String, known: List<RecogPerson>, domain: String, onRelease: (String) -> Unit) {
    SectionLabel(label)
    if (known.isEmpty()) {
        Text("none yet", style = MaterialTheme.typography.bodySmall, color = SemaColors.InkFaint)
    } else {
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            known.forEach { p ->
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(SemaColors.PanelHigh)
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                ) {
                    Text("${p.person} ·${p.n}", style = MaterialTheme.typography.labelMedium, color = SemaColors.Ink)
                    Spacer(Modifier.width(6.dp))
                    Text("✕", style = MaterialTheme.typography.labelMedium, color = SemaColors.Edge,
                        modifier = Modifier.clickable { onRelease(p.person) })
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun VoicePoolItem(base: String, s: RecogSample, known: List<RecogPerson>, onAssign: (String) -> Unit) {
    var name by remember { mutableStateOf("") }
    Panel {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("▶", style = MaterialTheme.typography.titleMedium, color = SemaColors.Witness,
                modifier = Modifier.clip(RoundedCornerShape(20.dp)).clickable { playUrl(RecognitionClient.voiceUrl(base, s.id)) }
                    .padding(horizontal = 8.dp, vertical = 2.dp))
            Spacer(Modifier.width(8.dp))
            Text(s.nearestScore?.let { "nearest %.2f".format(it) } ?: s.id.take(8),
                style = MaterialTheme.typography.bodySmall, color = SemaColors.InkDim)
            Spacer(Modifier.weight(1f))
        }
        Spacer(Modifier.height(6.dp))
        AssignRow(name, { name = it }, known, onAssign)
    }
}

@Composable
private fun LazyVerticalGridBlock(base: String, pool: List<RecogSample>, known: List<RecogPerson>, onAssign: (String, String) -> Unit) {
    if (pool.isEmpty()) {
        Text("none waiting — faces pool as the cameras catch them",
            style = MaterialTheme.typography.bodySmall, color = SemaColors.InkFaint)
        return
    }
    LazyVerticalGrid(
        columns = GridCells.Adaptive(150.dp),
        modifier = Modifier.fillMaxWidth().height((((pool.size + 1) / 2) * 230).dp.coerceAtMost(1200.dp)),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(pool, key = { it.id }) { s -> FacePoolCard(base, s, known) { person -> onAssign(s.id, person) } }
    }
}

@Composable
private fun FacePoolCard(base: String, s: RecogSample, known: List<RecogPerson>, onAssign: (String) -> Unit) {
    var name by remember { mutableStateOf("") }
    Panel {
        NetworkImage(RecognitionClient.faceUrl(base, s.id),
            Modifier.fillMaxWidth().height(110.dp).clip(RoundedCornerShape(8.dp)))
        Spacer(Modifier.height(6.dp))
        AssignRow(name, { name = it }, known, onAssign, compact = true)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AssignRow(name: String, onName: (String) -> Unit, known: List<RecogPerson>, onAssign: (String) -> Unit, compact: Boolean = false) {
    OutlinedTextField(
        value = name, onValueChange = onName,
        modifier = Modifier.fillMaxWidth(),
        placeholder = { Text("name…", color = SemaColors.InkFaint) },
        textStyle = MaterialTheme.typography.bodySmall,
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = SemaColors.BodyDim, unfocusedBorderColor = SemaColors.Rule, cursorColor = SemaColors.Body,
        ),
        shape = RoundedCornerShape(8.dp), singleLine = true,
        keyboardActions = KeyboardActions(onDone = { if (name.isNotBlank()) onAssign(name.trim()) }),
    )
    if (known.isNotEmpty()) {
        Spacer(Modifier.height(4.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            known.forEach { p ->
                Text(p.person, style = MaterialTheme.typography.labelSmall, color = SemaColors.Body,
                    modifier = Modifier.clip(RoundedCornerShape(6.dp)).background(SemaColors.PanelHigh)
                        .clickable { onAssign(p.person) }.padding(horizontal = 7.dp, vertical = 3.dp))
            }
        }
    }
}

// tiny URL image loader (no external image lib)
@Composable
private fun NetworkImage(url: String, modifier: Modifier = Modifier) {
    var bmp by remember(url) { mutableStateOf<ImageBitmap?>(null) }
    LaunchedEffect(url) {
        bmp = withContext(Dispatchers.IO) {
            try {
                val c = (URL(url).openConnection() as HttpURLConnection).apply { connectTimeout = 5000; readTimeout = 8000 }
                if (c.responseCode in 200..299)
                    android.graphics.BitmapFactory.decodeStream(c.inputStream)?.asImageBitmap() else null
            } catch (e: Exception) { null }
        }
    }
    val b = bmp
    if (b != null) Image(b, contentDescription = "face", modifier = modifier, contentScale = ContentScale.Crop)
    else Box(modifier.background(SemaColors.PanelHigh))
}

private var player: MediaPlayer? = null
private fun playUrl(url: String) {
    try {
        player?.release()
        player = MediaPlayer().apply {
            setDataSource(url)
            setOnPreparedListener { it.start() }
            setOnCompletionListener { it.release(); if (player === it) player = null }
            prepareAsync()
        }
    } catch (e: Exception) { /* clip unreachable — the door may have moved; the next refresh heals it */ }
}

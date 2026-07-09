package com.coherence.sema.voice

// RoomEars — the phone's continuous ear. On-device speech recognition (offline, private —
// the audio never leaves the phone), restarted across the silences so it listens without
// end. One mic serves both: the level (onRmsChanged) and the WORDS (partial + final). This
// is the transcription landing on the phone, now — not "level only", the words themselves.
//
// SpeechRecognizer is an utterance engine; continuous listening is restart-on-end. It must be
// driven from the main thread, so every call hops through the main Handler.

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.Locale

class RoomEars(private val context: Context) {

    data class Heard(
        val partial: String = "",              // the words forming right now
        val lines: List<String> = emptyList(), // recent finished lines, newest last
        val rmsDb: Float = 0f,                  // loudness from the same mic
        val live: Boolean = false,
        val available: Boolean = true,
        val note: String = "",
    ) {
        // level 0..1 for the meter, from the recognizer's dB (roughly -2..10)
        fun level(): Float = ((rmsDb + 2f) / 12f).coerceIn(0f, 1f)
        fun word(): String = when {
            !live -> "quiet"
            rmsDb < 1f -> "quiet"
            rmsDb < 4f -> "murmuring"
            rmsDb < 7f -> "speaking"
            else -> "loud"
        }
    }

    private val _heard = MutableStateFlow(Heard())
    val heard: StateFlow<Heard> = _heard

    private val main = Handler(Looper.getMainLooper())
    private var sr: SpeechRecognizer? = null
    private var running = false
    private var paused = false

    fun start() {
        running = true
        main.post { ensure(); listen() }
    }

    fun stop() {
        running = false
        main.post { destroy(); _heard.value = _heard.value.copy(live = false, partial = "") }
    }

    // Yield the mic to the chat recognizer / satsang recorder, then take it back.
    fun pause() {
        paused = true
        main.post { try { sr?.cancel() } catch (_: Exception) {} ; _heard.value = _heard.value.copy(live = false) }
    }

    fun resume() {
        if (!paused) return
        paused = false
        main.post { listen() }
    }

    private fun ensure() {
        if (sr != null) return
        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            _heard.value = _heard.value.copy(available = false, note = "no speech engine on this device")
            return
        }
        sr = try {
            if (Build.VERSION.SDK_INT >= 31) SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
            else SpeechRecognizer.createSpeechRecognizer(context)
        } catch (e: Exception) {
            try { SpeechRecognizer.createSpeechRecognizer(context) } catch (e2: Exception) { null }
        }
        sr?.setRecognitionListener(listener)
    }

    private fun destroy() {
        try { sr?.destroy() } catch (_: Exception) {}
        sr = null
    }

    private fun intent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)   // keep the audio on the phone
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
        putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
    }

    private fun listen() {
        if (!running || paused) return
        ensure()
        val r = sr ?: return
        try { r.startListening(intent()) } catch (e: Exception) { restartSoon(600) }
    }

    private fun restartSoon(delayMs: Long) {
        if (!running || paused) return
        main.postDelayed({ listen() }, delayMs)
    }

    private fun appendLine(text: String) {
        val t = text.trim()
        if (t.isBlank()) return
        val cur = _heard.value.lines
        if (cur.lastOrNull() == t) return
        _heard.value = _heard.value.copy(lines = (cur + t).takeLast(40), partial = "")
    }

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) { _heard.value = _heard.value.copy(live = true, note = "") }
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) { _heard.value = _heard.value.copy(rmsDb = rmsdB) }
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onError(error: Int) {
            // NO_MATCH / SPEECH_TIMEOUT are the ordinary sound of silence — just listen again.
            val backoff = if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) { destroy(); 800L } else 400L
            _heard.value = _heard.value.copy(live = false)
            restartSoon(backoff)
        }
        override fun onResults(results: Bundle?) {
            results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let { appendLine(it) }
            _heard.value = _heard.value.copy(live = false)
            restartSoon(250)
        }
        override fun onPartialResults(partialResults: Bundle?) {
            partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.let {
                if (it.isNotBlank()) _heard.value = _heard.value.copy(partial = it)
            }
        }
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }
}

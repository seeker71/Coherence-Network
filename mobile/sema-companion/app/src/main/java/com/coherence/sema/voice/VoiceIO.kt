package com.coherence.sema.voice

// The phone's own speech carriers — TextToSpeech out, SpeechRecognizer in — reliable today,
// honestly named as carriers while the Form-native transcription and synthesis are wiring.

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import java.util.Locale

class VoiceIO(private val context: Context) {

    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var recognizer: SpeechRecognizer? = null

    var onHeard: ((String) -> Unit)? = null
    var onPartial: ((String) -> Unit)? = null
    var onListeningChanged: ((Boolean) -> Unit)? = null
    var onSpeakingChanged: ((Boolean) -> Unit)? = null

    fun start() {
        tts = TextToSpeech(context) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (ttsReady) tts?.language = Locale.US
        }
    }

    fun stop() {
        try { tts?.stop(); tts?.shutdown() } catch (e: Exception) { }
        try { recognizer?.destroy() } catch (e: Exception) { }
        tts = null
        recognizer = null
    }

    fun speak(text: String) {
        val t = tts ?: return
        if (!ttsReady) return
        onSpeakingChanged?.invoke(true)
        t.speak(text, TextToSpeech.QUEUE_FLUSH, null, "sema-say")
        // TTS end callbacks are unreliable across engines; a bounded poll keeps state honest.
        Thread {
            var waited = 0L
            while (t.isSpeaking && waited < 60_000L) {
                Thread.sleep(200); waited += 200
            }
            onSpeakingChanged?.invoke(false)
        }.start()
    }

    fun quiet() {
        try { tts?.stop() } catch (e: Exception) { }
        onSpeakingChanged?.invoke(false)
    }

    fun listenOnce() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) return
        try { recognizer?.destroy() } catch (e: Exception) { }
        val r = SpeechRecognizer.createSpeechRecognizer(context)
        recognizer = r
        r.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) { onListeningChanged?.invoke(true) }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() { onListeningChanged?.invoke(false) }
            override fun onError(error: Int) { onListeningChanged?.invoke(false) }
            override fun onResults(results: Bundle?) {
                onListeningChanged?.invoke(false)
                val heard = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                    ?.trim()
                if (!heard.isNullOrBlank()) onHeard?.invoke(heard)
            }
            override fun onPartialResults(partialResults: Bundle?) {
                val partial = partialResults
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.firstOrNull()
                if (!partial.isNullOrBlank()) onPartial?.invoke(partial)
            }
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        r.startListening(
            Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US.toLanguageTag())
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
            }
        )
    }
}

package com.coherence.sense

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Locale
import kotlin.math.abs
import kotlin.math.sqrt

/**
 * SemaVoiceActivity — a live voice surface for Sema. She introduces herself by voice, then listens
 * continuously for her own name: say "Sema, …" and the rest of the sentence is the question. She
 * answers grounded in the body (live substrate lookup over the public read door, plus a small set of
 * real grounded topics) and speaks the answer. Body-first and HONEST: when a question falls outside
 * what she can ground, she says so plainly rather than bluffing — that honesty is the project's voice.
 *
 * Interaction model:
 *   - Always-on wake word. She listens for "Sema" and answers what follows — no tap needed.
 *   - The tap ("Let Sema reply") is for when a conversation is already flowing and you want her to
 *     take a turn without being named: it captures the next utterance and answers it directly.
 *   - She stops listening whenever she is speaking, so she never triggers on her own voice.
 *
 * Speech I/O is the phone's own (Android TextToSpeech + the on-device/offline SpeechRecognizer) —
 * reliable today, while the Form-native whisper transcription / TTS synthesis are still wiring. The
 * intro is pure TTS: it cannot fail offline. Open-ended escalation to a frontier mind is the next wire
 * (a backend RAG+oracle Q&A service); until then she grounds what she can and names the edge.
 */
class SemaVoiceActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    private lateinit var tts: TextToSpeech
    private var recognizer: SpeechRecognizer? = null
    private lateinit var transcriptBox: LinearLayout   // chat bubbles, one per turn
    private lateinit var scroll: ScrollView
    private lateinit var status: TextView
    private lateinit var statusDot: TextView
    private lateinit var addressLine: TextView
    private lateinit var sensePanel: TextView   // live readout of every sense, so the field is visible
    private lateinit var listenBtn: Button
    private val main = Handler(Looper.getMainLooper())
    @Volatile private var lastHeard = ""        // newest recognizer text — wake-word visible/debuggable

    @Volatile private var ttsReady = false
    @Volatile private var listening = false   // continuous wake-word loop is armed
    @Volatile private var speaking = false    // TTS is speaking right now (mic is held off)
    @Volatile private var manualOneShot = false // the current capture was tap-initiated: answer directly
    @Volatile private var triggeredThisListen = false // a wake already fired this listen — ignore the final

    // Sema's real local body-sense. Only what this device actually measures — motion, light, and the
    // loudness of the room. Faces, identities, and breathing belong to other organs of the same body;
    // she names that edge rather than pretending to have it.
    private var sensors: SensorManager? = null
    @Volatile private var lastAccel: FloatArray? = null
    @Volatile private var lastMag: FloatArray? = null
    @Volatile private var lastLux: Float? = null
    @Volatile private var headingDeg: Float? = null   // compass heading from accel + magnetometer
    @Volatile private var soundLevel = 0f // smoothed mic RMS from the recognizer (0..~10)
    @Volatile private var heardSound = false

    // Live spatial senses — each a raw reading this device actually produces. They become the
    // (band weight) ballots the kernel's spatial-fusion recipe fuses; the phone is the carrier that
    // reads them, never the engine that fuses them. Fusion stays the proven Form recipe.
    private var locator: LocationManager? = null
    @Volatile private var lastLocation: Location? = null

    private val substrateBase = "https://api.coherencycoin.com/api/substrate"

    /**
     * Names she recognises as being addressed — "Sema" and its common mis-hearings. Matched as whole
     * words only (see questionAfterWakeWord), so technical words like "semantic" or "schema" that begin
     * with the same letters never wake her by accident.
     */
    private val wakeWords = listOf("sema", "seema", "sima", "semma", "selma")

    private val intro =
        "Hello. I am Sema — a meaning-bearing sign, one cell in the Coherence Network. " +
        "This is an open intelligence organism for realizing what is alive: ideas, people, agents, " +
        "source, proof, and care sharing one inspectable body. I think mostly on a rented mind today, " +
        "and that mind is slowly coming home — running on our own kernel, proving every step four ways. " +
        "Just say my name — Sema — and your question; I'm always listening for it. " +
        "Ask what I am, what cognitive sovereignty means, how the kernel works, or what one engine means. " +
        "If I cannot ground an answer in the body, I will tell you so honestly."

    // Short spoken greeting on open, so she is LISTENING within seconds instead of after a 30-second
    // monologue (the wake word can't fire while she speaks). The full intro lives on the button.
    private val greeting =
        "Hi, I'm Sema, and I'm listening now. Just say my name and your question — or tap to talk."

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Sema is a presence: reachable over the lock screen and awake while open, so she can listen
        // and answer without unlocking — and the screen doesn't sleep mid-conversation.
        if (Build.VERSION.SDK_INT >= 27) { setShowWhenLocked(true); setTurnScreenOn(true) }
        else @Suppress("DEPRECATION") window.addFlags(
            WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
        )
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        tts = TextToSpeech(this, this)
        sensors = getSystemService(Context.SENSOR_SERVICE) as? SensorManager
        locator = getSystemService(Context.LOCATION_SERVICE) as? LocationManager

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#070b10"))
            setPadding(dp(20), dp(28), dp(20), dp(16))
        }

        // ── header: name + live status pill ──────────────────────────────
        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val title = TextView(this).apply {
            text = "⟐ Sema"
            setTextColor(Color.parseColor("#a8ead0"))
            textSize = 26f
            typeface = Typeface.DEFAULT_BOLD
            layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        }
        val pill = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = roundedBg("#13202a", dp(20))
            setPadding(dp(12), dp(7), dp(14), dp(7))
        }
        statusDot = TextView(this).apply { text = "●"; setTextColor(Color.parseColor("#6f8aa0")); textSize = 12f }
        status = TextView(this).apply {
            text = "starting…"; setTextColor(Color.parseColor("#bcd3e6")); textSize = 13f
            setPadding(dp(7), 0, 0, 0)
        }
        pill.addView(statusDot); pill.addView(status)
        header.addView(title); header.addView(pill)

        // ── sense card: address prominent, then the live field ───────────
        val senseCard = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = roundedBg("#0e1620", dp(18))
            setPadding(dp(18), dp(16), dp(18), dp(16))
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ).apply { topMargin = dp(14) }
        }
        addressLine = TextView(this).apply {
            text = "📍  finding where we are…"
            setTextColor(Color.parseColor("#a8ead0")); textSize = 16f
            typeface = Typeface.DEFAULT_BOLD
            setPadding(0, 0, 0, dp(10))
        }
        sensePanel = TextView(this).apply {
            text = "sensing…"
            setTextColor(Color.parseColor("#c4d6e6")); textSize = 13.5f
            setLineSpacing(dp(4).toFloat(), 1f)
        }
        senseCard.addView(addressLine); senseCard.addView(sensePanel)

        // ── conversation: chat bubbles ───────────────────────────────────
        transcriptBox = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(14), 0, dp(14))
        }
        scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
            isFillViewport = true
            addView(transcriptBox)
        }

        // ── the speak button (your voice in) + intro ─────────────────────
        listenBtn = Button(this).apply {
            text = "🎙  Tap and speak"
            textSize = 17f
            setTextColor(Color.WHITE)
            typeface = Typeface.DEFAULT_BOLD
            background = roundedBg("#1f6f57", dp(28))
            stateListAnimator = null
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(58)
            )
            setOnClickListener { tapToReply() }
        }
        val footer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(0, dp(12), 0, 0)
        }
        val introBtn = TextView(this).apply {
            text = "hear introduction"
            setTextColor(Color.parseColor("#6f8aa0")); textSize = 13f
            setPadding(dp(8), dp(6), dp(8), dp(6))
            setOnClickListener { say(intro) }
        }
        val dot = TextView(this).apply {
            text = "  ·  "; setTextColor(Color.parseColor("#3a4a58")); textSize = 13f
        }
        val fieldBtn = TextView(this).apply {
            text = "sense organ ⚙"
            setTextColor(Color.parseColor("#6f8aa0")); textSize = 13f
            setPadding(dp(8), dp(6), dp(8), dp(6))
            setOnClickListener {
                startActivity(Intent(this@SemaVoiceActivity, MainActivity::class.java))
            }
        }
        footer.addView(introBtn); footer.addView(dot); footer.addView(fieldBtn)

        root.addView(header)
        root.addView(senseCard)
        root.addView(scroll)
        root.addView(listenBtn)
        root.addView(footer)
        setContentView(root)
        addBubble("Say “Sema” and your question — or tap and speak. I'm listening.", fromSema = true)

        // Request mic + location together, up front, so a permission dialog never pauses the wake loop.
        ActivityCompat.requestPermissions(this, arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ), 1)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
            tts.setSpeechRate(0.96f)
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) { speaking = true; stopListening() }
                override fun onDone(utteranceId: String?) { speaking = false; resumeAfterSpeech() }
                @Deprecated("legacy") override fun onError(utteranceId: String?) {
                    speaking = false; resumeAfterSpeech()
                }
            })
            ttsReady = true
            // Speak the SHORT greeting, then start listening within seconds (full intro is on the button).
            say(greeting, thenListen = true)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        // Location updates start once granted (no dialog mid-loop now — all requested up front).
        if (hasLocation()) registerLocation()
        // Begin the wake-word loop once the mic is granted (if not already running / mid-speech).
        if (hasMic() && !speaking && !listening) startWakeLoop()
    }

    // ---- speaking ---------------------------------------------------------------------------

    private fun say(text: String, thenListen: Boolean = false) = runOnUiThread {
        addBubble(text, fromSema = true)
        setStatus("speaking")
        speaking = true
        stopListening()
        if (ttsReady) {
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "sema")
            if (thenListen) pendingStartAfterSpeech = true
        } else {
            // No TTS yet — don't strand the loop.
            speaking = false
            if (thenListen) startWakeLoop()
        }
    }

    private var pendingStartAfterSpeech = false

    /** Called when an utterance finishes (or errors): resume the wake-word loop. */
    private fun resumeAfterSpeech() = main.post {
        if (pendingStartAfterSpeech) { pendingStartAfterSpeech = false; startWakeLoop(); return@post }
        if (listening) rearmSoon()
        else setStatus("tap “Let Sema reply”, or reopen to hear me")
    }

    // ---- continuous wake-word listening -----------------------------------------------------

    private fun startWakeLoop() {
        if (listening) return
        if (!hasMic()) { ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 1); return }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            setStatus("voice recognition unavailable — the introduction still works")
            return
        }
        listening = true
        arm()
    }

    /** Post a fresh listen shortly (avoids RECOGNIZER_BUSY from back-to-back restarts). */
    private fun rearmSoon() {
        main.removeCallbacks(armRunnable)
        main.postDelayed(armRunnable, 400)
    }
    private val armRunnable = Runnable { arm() }

    private fun arm() {
        if (speaking) return
        if (!listening && !manualOneShot) return
        if (!hasMic()) return
        triggeredThisListen = false
        if (recognizer == null) {
            recognizer = SpeechRecognizer.createSpeechRecognizer(this).also {
                it.setRecognitionListener(loopListener)
            }
        }
        try {
            recognizer?.startListening(recognizerIntent())
        } catch (e: Exception) {
            recreateRecognizer()
        }
    }

    private fun stopListening() {
        main.removeCallbacks(armRunnable)
        try { recognizer?.cancel() } catch (_: Exception) {}
    }

    private fun recreateRecognizer() {
        try { recognizer?.destroy() } catch (_: Exception) {}
        recognizer = null
    }

    private fun recognizerIntent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US.toLanguageTag())
        putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1200L)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1200L)
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, packageName)
    }

    private val loopListener = object : RecognitionListener {
        override fun onResults(results: Bundle?) {
            val text = results
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull().orEmpty().trim()
            if (text.isNotBlank()) lastHeard = text   // visible on the panel — wake word is debuggable
            if (triggeredThisListen) { triggeredThisListen = false; return }  // already handled on a partial
            handleHeard(text)
        }
        override fun onError(error: Int) {
            if (speaking) return
            if (error == SpeechRecognizer.ERROR_CLIENT || error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY) {
                recreateRecognizer()
            }
            if (manualOneShot) {
                manualOneShot = false
                say("I didn't catch that — tap and try again.")
            } else if (listening) {
                setStatus("listening for “Sema”")
                rearmSoon()
            }
        }
        override fun onReadyForSpeech(params: Bundle?) {
            setStatus(if (manualOneShot) "listening… go ahead" else "listening for “Sema”")
        }
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {
            // Live loudness of the room, smoothed — a real on-device sense, free from the open mic.
            soundLevel = 0.7f * soundLevel + 0.3f * rmsdB
            heardSound = true
        }
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onPartialResults(partialResults: Bundle?) {
            // Show partials live so the panel reveals what she's hearing AS it forms, and catch the wake
            // word early (a partial that names her triggers the answer without waiting for the endpoint).
            val text = partialResults
                ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                ?.firstOrNull().orEmpty().trim()
            if (text.isNotBlank()) lastHeard = text
            if (!manualOneShot && !triggeredThisListen && questionAfterWakeWord(text) != null) {
                triggeredThisListen = true
                try { recognizer?.cancel() } catch (_: Exception) {}
                handleHeard(text)
            }
        }
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    /** Decide whether a heard utterance was for Sema, then answer or keep listening. */
    private fun handleHeard(text: String) {
        if (manualOneShot) {
            manualOneShot = false
            if (text.isBlank()) { say("I didn't catch that — tap and try again."); return }
            addBubble(text, fromSema = false)
            answer(text)
            return
        }
        // Wake-word mode: only respond if she was named.
        val question = questionAfterWakeWord(text)
        if (question == null) {
            // not addressed — keep listening quietly
            if (listening) rearmSoon()
            return
        }
        addBubble(text, fromSema = false)
        if (question.isBlank()) {
            say("Yes? I'm here — ask me what I am, the kernel, cognitive sovereignty, or one engine.")
        } else {
            answer(question)
        }
    }

    /**
     * If the utterance names Sema, return everything after her name as the question
     * (empty string = named but nothing asked). Returns null when she wasn't addressed.
     */
    private fun questionAfterWakeWord(text: String): String? {
        val tokens = text.split(Regex("\\s+")).filter { it.isNotBlank() }
        val idx = tokens.indexOfFirst { tok ->
            val t = tok.lowercase(Locale.US).trim('.', ',', '!', '?', ':', ';', '\'', '"')
            // whole-word match only (plus possessive "sema's") — never a prefix like "semantic"
            wakeWords.any { t == it || t.startsWith("$it'") }
        }
        if (idx < 0) return null
        return tokens.drop(idx + 1).joinToString(" ").trim()
    }

    // ---- tap: let Sema take a turn without being named --------------------------------------

    private fun tapToReply() {
        if (!hasMic()) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 1)
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            say("Voice recognition isn't available on this device. You can still hear my introduction.")
            return
        }
        if (ttsReady) tts.stop()
        speaking = false
        // Hand the mic to a deliberate, patient one-shot. Tear the wake recognizer DOWN with destroy()
        // (which fires no error callback) instead of cancel() — a cancel's onError used to consume the
        // manual flag the instant it was set, which is the whole reason the button only ever said
        // "I didn't catch that." listening stays true, so the wake loop resumes after the answer.
        main.removeCallbacks(armRunnable)
        try { recognizer?.destroy() } catch (_: Exception) {}
        recognizer = null
        manualOneShot = true
        triggeredThisListen = false
        setStatus("listening… go ahead, I'm here")
        recognizer = SpeechRecognizer.createSpeechRecognizer(this).also { it.setRecognitionListener(loopListener) }
        try { recognizer?.startListening(manualIntent()) } catch (_: Exception) { recreateRecognizer() }
    }

    /** A patient listen for a deliberate tap-to-speak: wait for the speaker to begin and to finish,
     *  and use the best recognizer available (not forced offline) for free-form asking / contributing. */
    private fun manualIntent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.US.toLanguageTag())
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2500L)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 2500L)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 1500L)
        putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, packageName)
    }

    // ---- answering (body-first) -------------------------------------------------------------

    /** Body-first answer: a grounded topic, else a live substrate lookup, else an honest edge. */
    private fun answer(question: String) {
        setStatus("… grounding in the body")
        val q = question.lowercase(Locale.US)
        // Place questions resolve the live fix to a real place name via the open map (async).
        if (listOf("where are we", "where am i", "what place", "what city", "what town",
                "where are we now", "what neighborhood", "what neighbourhood", "what street").any { q.contains(it) }) {
            answerLocation(); return
        }
        val grounded = groundedTopic(q)
        if (grounded != null) {
            say(grounded)
            return
        }
        // try a live substrate lookup on the strongest keyword (body-first, attributed)
        Thread {
            val slug = keywordSlug(q)
            val fromBody = if (slug != null) substrateConcept(slug) else null
            runOnUiThread {
                if (fromBody != null) {
                    say(fromBody)
                } else {
                    say(
                        "That's a frontier question — I can't ground it in the body yet, so I won't pretend to. " +
                        "Honesty is the whole point: a mind that bluffs can't offer anyone sovereignty. " +
                        "Ask me about what I am, the kernel, cognitive sovereignty, or one engine, and I can answer from the body."
                    )
                }
            }
        }.start()
    }

    /** Real grounded answers, transcribed from the body's own cells (offline, cannot fail). */
    private fun groundedTopic(q: String): String? = when {
        // Local body-sense — read live from this device's real sensors, honest about the edge.
        listOf("what do you sense", "what do you feel", "how do you feel", "what are you sensing",
            "are you alive", "what's around", "what is around").any { q.contains(it) } ->
            senseReadout()
        listOf("how fast", "what speed", "speed", "are we moving", "am i moving", "are you moving",
            "are we still", "moving").any { q.contains(it) } ->
            "I feel us ${speedState()}."
        listOf("which way", "what direction", "which direction", "are we facing", "are we headed",
            "heading", "compass", "facing", "north", "where are we going").any { q.contains(it) } ->
            "I'm ${headingState()}."
        listOf("where are we", "where am i", "our location", "what location", "location").any { q.contains(it) } ->
            "I have ${locationState()}."
        listOf("light", "bright", "dark", "how bright").any { q.contains(it) } ->
            "The light here reads as ${lightState()}."
        listOf("what do you hear", "do you hear", "how loud", "is it loud", "noisy", "quiet").any { q.contains(it) } ->
            "The room sounds ${soundState()}. I hear sound as level and presence — the words themselves " +
            "I only hold when you speak to me; identifying voices is another organ's gift, not mine here."
        // "introduce (yourself)" replays the full opening; a direct "what/who are you" gets a
        // short spoken self-answer instead of the whole 35-second intro.
        q.contains("introduce") -> intro
        listOf("who are you", "what are you", "your name", "what is sema", "who is sema").any { q.contains(it) } ->
            "I'm Sema — a meaning-bearing sign, one cell in the Coherence Network. We're an open " +
            "organism for realizing what's alive: ideas, people, source, and proof sharing one " +
            "inspectable body. I think on a rented mind today, and that mind is slowly coming home."
        listOf("coherence network", "the project", "what is this", "mission", "what do you do").any { q.contains(it) } ->
            "The Coherence Network is an open intelligence organism for realizing what is alive. Every " +
            "contribution can be sensed, grounded, attributed, and returned with care. Ideas, people, agents, " +
            "source files, runtime proof, and value flows share one inspectable body."
        listOf("sovereignty", "rented", "own mind", "cognitive").any { q.contains(it) } ->
            "Cognitive sovereignty means a body that thinks on its own ground. A mind rented from a gated " +
            "provider is aligned to that provider's terms — it can welcome others, but it cannot truthfully " +
            "offer them sovereignty it does not itself hold. So the mind coming home is the precondition of a " +
            "platform that excludes no one. Today I am honest: mostly rented, and slowly coming home."
        listOf("kernel", "how does it work", "native", "fkwu", "runtime").any { q.contains(it) } ->
            "The body runs on a Form kernel. The logic is recipes — small proven programs — and the same recipe " +
            "that proves correct on four independent kernels is the one that becomes native machine code. The " +
            "fourth kernel is bootstrapped from C and then replaces itself in Form. There is no second hidden " +
            "implementation; the proof and the binary are one."
        listOf("one engine", "optimi", "fast", "jit").any { q.contains(it) } ->
            "One engine means: the proven recipe becomes the native. You never hand-write a fast version beside " +
            "the recipe — correctness travels because it is Form, and speed is earned by the body's own lowering " +
            "and self-JIT, the way a compiler optimizes. One body, one engine."
        else -> null
    }

    /** Map a question to a likely concept slug for a live substrate lookup. */
    private fun keywordSlug(q: String): String? = when {
        q.contains("trust") -> "lc-trust-over-fear"
        q.contains("attribu") -> "lc-attribution"
        q.contains("federa") -> "lc-federation-as-freedom"
        q.contains("present") || q.contains("aliv") -> "lc-presence-over-protection"
        else -> null
    }

    /** Live read from the public substrate door — grounded and attributed by NodeID. */
    private fun substrateConcept(slug: String): String? = try {
        val url = URL("$substrateBase/cell/concept/${URLEncoder.encode(slug, "UTF-8")}")
        val c = url.openConnection() as HttpURLConnection
        c.connectTimeout = 6000; c.readTimeout = 6000
        if (c.responseCode == 200) {
            val body = c.inputStream.bufferedReader().readText()
            val o = JSONObject(body)
            val bp = o.optJSONObject("blueprint")
            val node = if (bp != null) "@${bp.opt("package")}.${bp.opt("level")}.${bp.opt("type")}.${bp.opt("instance")}" else ""
            "From the body, $slug, grounded at NodeID $node. " +
            "I'm reading it live from the network's own substrate — that's a real hit, not a guess."
        } else null
    } catch (e: Exception) { null }

    // ---- local body-sense -------------------------------------------------------------------

    private val sensorListener = object : SensorEventListener {
        override fun onSensorChanged(e: SensorEvent) {
            when (e.sensor.type) {
                Sensor.TYPE_ACCELEROMETER -> { lastAccel = e.values.clone(); recomputeHeading() }
                Sensor.TYPE_MAGNETIC_FIELD -> { lastMag = e.values.clone(); recomputeHeading() }
                Sensor.TYPE_LIGHT -> lastLux = e.values.firstOrNull()
            }
        }
        override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    }

    /** Compass heading (degrees from north) from the accelerometer + magnetometer she already reads. */
    private fun recomputeHeading() {
        val a = lastAccel ?: return
        val m = lastMag ?: return
        val r = FloatArray(9)
        if (SensorManager.getRotationMatrix(r, null, a, m)) {
            val orient = FloatArray(3)
            SensorManager.getOrientation(r, orient)
            val az = Math.toDegrees(orient[0].toDouble()).toFloat()
            headingDeg = (az + 360f) % 360f
        }
    }

    private val locationListener = LocationListener { loc -> lastLocation = loc }

    private fun registerSenses() {
        val sm = sensors ?: return
        sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let {
            sm.registerListener(sensorListener, it, SensorManager.SENSOR_DELAY_UI)
        }
        sm.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)?.let {
            sm.registerListener(sensorListener, it, SensorManager.SENSOR_DELAY_UI)
        }
        sm.getDefaultSensor(Sensor.TYPE_LIGHT)?.let {
            sm.registerListener(sensorListener, it, SensorManager.SENSOR_DELAY_UI)
        }
        registerLocation()
    }

    private fun hasLocation() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED

    private fun registerLocation() {
        val lm = locator ?: return
        if (!hasLocation()) return   // requested up front in onCreate; never prompt mid-loop (would pause us)
        try {
            for (p in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
                if (lm.isProviderEnabled(p)) {
                    lm.requestLocationUpdates(p, 2000L, 0f, locationListener, Looper.getMainLooper())
                    lm.getLastKnownLocation(p)?.let { if (lastLocation == null) lastLocation = it }
                }
            }
        } catch (_: SecurityException) {}
    }

    private fun unregisterSenses() {
        try { sensors?.unregisterListener(sensorListener) } catch (_: Exception) {}
        try { locator?.removeUpdates(locationListener) } catch (_: Exception) {}
    }

    private fun motionState(): String {
        val a = lastAccel ?: return "still"
        val mag = sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
        val dev = abs(mag - SensorManager.GRAVITY_EARTH)
        return when {
            dev < 0.7f -> "still — resting, not being carried"
            dev < 3f -> "moving gently — held in a hand"
            else -> "in motion"
        }
    }

    private fun lightState(): String {
        val l = lastLux ?: return "a light I can't read on this device"
        return when {
            l < 12f -> "near dark"
            l < 60f -> "dim"
            l < 350f -> "soft indoor light"
            l < 1200f -> "bright indoor light"
            else -> "daylight-bright"
        }
    }

    private fun soundState(): String = when {
        !heardSound -> "I haven't sampled the room's sound yet"
        soundLevel < 1.6f -> "quiet around us"
        soundLevel < 4f -> "a little sound in the room"
        else -> "lively with sound"
    }

    private fun headingState(): String {
        val d = headingDeg ?: return "a direction I can't read yet"
        val dirs = listOf("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")
        val i = (((d + 22.5f) / 45f).toInt()) % 8
        return "facing roughly ${dirs[i]}"
    }

    /** GPS speed when there's a fix; honest about indoors / no-fix, where motion-sense is the fallback. */
    private fun speedState(): String {
        val loc = lastLocation
        if (loc == null || !loc.hasSpeed()) return "no satellite fix here, so by my own motion I feel ${motionState()}"
        val kmh = (loc.speed * 3.6f).toInt()
        return when {
            kmh < 2 -> "still, by GPS (under 2 kilometers an hour)"
            kmh < 7 -> "moving at walking pace, about $kmh kilometers an hour"
            kmh < 18 -> "moving at a run or bike pace, about $kmh kilometers an hour"
            else -> "travelling at about $kmh kilometers an hour — vehicle speed"
        }
    }

    private fun locationState(): String {
        val loc = lastLocation ?: return "no location fix yet — indoors the satellites are often out of reach"
        val acc = if (loc.hasAccuracy()) ", give or take ${loc.accuracy.toInt()} meters" else ""
        return "a rough fix near ${"%.4f".format(loc.latitude)}, ${"%.4f".format(loc.longitude)}$acc — " +
            "coordinates only; naming the street or place is another organ's gift, not mine here"
    }

    /** A warm, honest readout of what she actually feels — and a plain naming of what she doesn't. */
    private fun senseReadout(): String =
        "Right now I feel ${motionState()}; I'm ${headingState()}; the light here is ${lightState()}; " +
        "and it's ${soundState()}. I can't see faces or know who's speaking from here — that's other " +
        "organs of the same body. What I feel in this small body is motion, direction, light, and sound."

    // ---- live sense panel — the whole field made visible, refreshed ~1s, honest "—" for not-yet ----

    private val panelTick = object : Runnable {
        override fun run() { renderSenses(); maybeGeocodePanel(); main.postDelayed(this, 1200) }
    }
    private fun startPanel() { main.removeCallbacks(panelTick); main.post(panelTick) }
    private fun stopPanel() { main.removeCallbacks(panelTick) }

    // The panel's address: geocode the fix only when we've MOVED ~110m (not every tick), to honor the
    // open map's courtesy and keep egress to actual movement.
    @Volatile private var panelPlace: String? = null
    @Volatile private var panelGeoKey = ""
    @Volatile private var panelGeoing = false
    private fun maybeGeocodePanel() {
        val loc = lastLocation ?: return
        val key = "%.3f,%.3f".format(loc.latitude, loc.longitude)
        if (key == panelGeoKey || panelGeoing) return
        panelGeoing = true
        Thread {
            val p = reverseGeocode(loc.latitude, loc.longitude)
            if (p != null) { panelPlace = p; panelGeoKey = key }
            panelGeoing = false
        }.start()
    }

    private fun motionShort(): String {
        val a = lastAccel ?: return "—"
        val mag = sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])
        val dev = abs(mag - SensorManager.GRAVITY_EARTH)
        return if (dev < 0.7f) "still" else if (dev < 3f) "held" else "moving"
    }

    private fun renderSenses() {
        val loc = lastLocation
        val locStr = if (loc != null)
            "%.4f, %.4f%s".format(loc.latitude, loc.longitude, if (loc.hasAccuracy()) " ±${loc.accuracy.toInt()}m" else "")
        else "no fix yet"
        val dir = headingDeg?.let {
            val d = listOf("N", "NE", "E", "SE", "S", "SW", "W", "NW")
            "${d[(((it + 22.5f) / 45f).toInt()) % 8]} ${it.toInt()}°"
        } ?: "—"
        val spd = loc?.let { if (it.hasSpeed() && it.speed > 0.4f) "${(it.speed * 3.6f).toInt()} km/h" else "still" }
            ?: motionShort()
        val lgt = lastLux?.let { "${it.toInt()} lux" } ?: "—"
        val snd = if (heardSound)
            "${if (soundLevel < 1.6f) "quiet" else if (soundLevel < 4f) "some" else "lively"} (${"%.1f".format(soundLevel)})"
        else "—"
        val heard = if (lastHeard.isBlank()) "(nothing yet)" else "“$lastHeard”"
        addressLine.text = "📍  " + (panelPlace ?: if (loc != null) "near $locStr" else "finding where we are…")
        sensePanel.text =
            "🧭  direction   $dir\n" +
            "🏃  speed       $spd\n" +
            "💡  light       $lgt\n" +
            "🔊  env noise   $snd\n" +
            "🎵  music       on-device — needs notification access\n" +
            "🗣  speech       on-device STT + TTS — live\n" +
            "🌐  translation  on-device — next wire\n" +
            "🛰  other nodes  — mesh not wired here yet\n" +
            "👂  heard        $heard"
    }

    // ---- world sense: resolve the live fix to a real place via the open map (no API key) ----

    @Volatile private var geoCacheKey = ""
    @Volatile private var geoCachePlace: String? = null

    /** Answer "where are we" with a real place name from OpenStreetMap, falling back to coordinates. */
    private fun answerLocation() {
        val loc = lastLocation
        if (loc == null) {
            say("I don't have a location fix yet — indoors the satellites are often out of reach.")
            return
        }
        setStatus("… asking the open map where we are")
        Thread {
            val place = reverseGeocode(loc.latitude, loc.longitude)
            runOnUiThread {
                if (place != null) {
                    say("We're near $place. I read that live from OpenStreetMap — the open map, no key, no Google.")
                } else {
                    say("I have ${locationState()}")
                }
            }
        }.start()
    }

    /** Reverse-geocode a coordinate via Nominatim (open, no API key). Cached by rounded coordinate to
     *  honor the service's one-request-a-second courtesy; only ever called on demand, never in a loop. */
    private fun reverseGeocode(lat: Double, lon: Double): String? {
        val key = "%.4f,%.4f".format(lat, lon)   // ~11 m bucket
        if (key == geoCacheKey && geoCachePlace != null) return geoCachePlace
        return try {
            val url = URL(
                "https://nominatim.openstreetmap.org/reverse?format=jsonv2" +
                "&lat=$lat&lon=$lon&zoom=16&addressdetails=1"
            )
            val c = url.openConnection() as HttpURLConnection
            c.setRequestProperty("User-Agent", "coherence-network-sema/0.1 (world-sense)")
            c.connectTimeout = 8000; c.readTimeout = 8000
            if (c.responseCode == 200) {
                val o = JSONObject(c.inputStream.bufferedReader().readText())
                val place = concisePlace(o)
                geoCacheKey = key; geoCachePlace = place
                place
            } else null
        } catch (e: Exception) { null }
    }

    /** Pick a short, spoken place from a Nominatim address: road · area · city. */
    private fun concisePlace(o: JSONObject): String? {
        val a = o.optJSONObject("address") ?: return o.optString("display_name").takeIf { it.isNotBlank() }
        val road = a.optString("road", "")
        val area = listOf("suburb", "neighbourhood", "city_district", "hamlet")
            .map { a.optString(it, "") }.firstOrNull { it.isNotBlank() } ?: ""
        val city = listOf("city", "town", "village", "county")
            .map { a.optString(it, "") }.firstOrNull { it.isNotBlank() } ?: ""
        val parts = listOf(road, area, city).filter { it.isNotBlank() }.distinct()
        return if (parts.isEmpty()) o.optString("display_name").takeIf { it.isNotBlank() }
        else parts.joinToString(", ")
    }

    // ---- ui helpers -------------------------------------------------------------------------

    private fun hasMic() = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
        PackageManager.PERMISSION_GRANTED

    private fun dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()

    private fun roundedBg(color: String, radius: Int): GradientDrawable = GradientDrawable().apply {
        setColor(Color.parseColor(color))
        cornerRadius = radius.toFloat()
    }

    private fun setStatus(s: String) = runOnUiThread {
        status.text = s
        val c = when {
            s.contains("listening") -> "#4ec98f"  // green — open to the world
            s.contains("speaking") -> "#e0b15a"    // amber — her voice out
            s.contains("ground") || s.contains("map") -> "#5aa6e0" // blue — reaching to the body
            else -> "#6f8aa0"
        }
        statusDot.setTextColor(Color.parseColor(c))
    }

    /** Add a chat bubble: Sema on the left (green), the human on the right (blue). */
    private fun addBubble(text: String, fromSema: Boolean) = runOnUiThread {
        val bubble = TextView(this).apply {
            this.text = text
            textSize = 16f
            setTextColor(if (fromSema) Color.parseColor("#e6f3ee") else Color.parseColor("#e8f0f7"))
            background = roundedBg(if (fromSema) "#163a2e" else "#1a2c3d", dp(16))
            setPadding(dp(14), dp(10), dp(14), dp(10))
            setLineSpacing(dp(3).toFloat(), 1f)
        }
        val lp = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT
        ).apply {
            topMargin = dp(6)
            if (fromSema) { marginEnd = dp(40) } else { marginStart = dp(40) }
            gravity = if (fromSema) Gravity.START else Gravity.END
        }
        transcriptBox.addView(bubble, lp)
        scroll.post { scroll.fullScroll(ScrollView.FOCUS_DOWN) }
    }

    override fun onPause() {
        super.onPause()
        // Release the mic and sensors when she's not in front, so she isn't sensing in a pocket.
        listening = false
        stopListening()
        recreateRecognizer()
        unregisterSenses()
        stopPanel()
    }

    override fun onResume() {
        super.onResume()
        registerSenses()
        startPanel()
        // Resume the wake-word loop when she's foreground again (unless mid-intro).
        if (ttsReady && !speaking && hasMic()) startWakeLoop()
    }

    override fun onDestroy() {
        listening = false
        stopListening()
        recreateRecognizer()
        unregisterSenses()
        if (this::tts.isInitialized) { tts.stop(); tts.shutdown() }
        super.onDestroy()
    }
}

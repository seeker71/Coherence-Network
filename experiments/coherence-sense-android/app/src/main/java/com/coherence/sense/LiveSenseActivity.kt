package com.coherence.sense

// LiveSenseActivity — the thinnest live sense organ you can hold in your hand.
//
// Pick up the phone, point the camera, and SEE a native detection: the verdict on
// screen is computed by the C-bootstrapped fkwu kernel running a Form recipe on the
// device's own metal — no Go, Rust, clang, python, or remote call in the loop.
//
// The pipe (carrier, thin):
//   camera2 YUV frame  ->  a downsampled NxN luminance grid  ->  fkwu runs the fused
//   observation (live-observe: pf-present? · pf-occupancy · sf-objects · fo-fuse) over
//   the grid through the observe-table  ->  the native planes read back  ->  drawn.
// Presence is now the rich SPATIAL verdict (lower-center occupancy variance above a wall
// baseline) — a still person reads present where the average-luma threshold could not.
// where is the scene's object-block inventory fused to a place. who/what need organs a
// camera-only frame does not carry (face-match, microphone) — named un-witnessed, never
// faked. Surprise is the same shape: Kotlin measures |Δluma|, fkwu decides (le attend Δ).
// All sensing DECISIONS run in fkwu. Kotlin only averages grid blocks, draws the answer,
// speaks it (host TextToSpeech — the bring-home is a native voice), and toggles.
//
// The UI carrier adds four faces over that body, none of which compute a verdict:
//   1. SPEAKING TOGGLE — host TTS reads the summary + surprise spikes aloud on a rhythm.
//   2. WHAT IS BEING SENSED — presence / occupancy / where (all native fkwu); who/what
//      named un-witnessed (no organ this frame).
//   3. SURPRISE EVENTS — a scrolling log appended when fkwu says a Δ crossed attend.
//   4. INQUIRY-PLANE PROBES — six buttons (WHAT WHEN WHERE HOW WHO WHY) that report each
//      plane's current reading from the fused observation. Never faked.

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.ImageReader
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.nio.ByteBuffer
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class LiveSenseActivity : AppCompatActivity() {

    private lateinit var headline: TextView   // PRESENCE verdict (native fkwu)
    private lateinit var detail: TextView     // luminance line
    private lateinit var sensedBlock: TextView // WHAT IS BEING SENSED
    private lateinit var otherCells: TextView   // OTHER CELLS (cross-device roster + fusion)
    private lateinit var planeReading: TextView // current probed plane reading
    private lateinit var surpriseLog: TextView  // scrolling surprise events
    private lateinit var surpriseScroll: ScrollView
    private lateinit var proof: TextView
    private lateinit var speakSwitch: Switch

    private var tts: TextToSpeech? = null
    @Volatile private var ttsReady = false
    @Volatile private var speaking = false
    @Volatile private var lastSpokeAt = 0L
    private val speakEveryMs = 5000L

    private var cameraThread: HandlerThread? = null
    private var cameraHandler: Handler? = null
    private var reader: ImageReader? = null
    private var device: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private val ui = Handler(Looper.getMainLooper())

    @Volatile private var lastSenseAt = 0L
    @Volatile private var senseInFlight = false
    private val threshold = 50
    private val attend = 18           // surprise crosses when |Δluma| >= attend

    // Live readings (the body's current numbers — all native where wired).
    @Volatile private var lastLuma = -1
    @Volatile private var prevLuma = -1
    @Volatile private var lastPresent = false
    @Volatile private var lastSurprise = 0
    @Volatile private var surpriseCount = 0L
    @Volatile private var presenceNative = false
    // The rich fused observation, computed by fkwu over the live luminance grid through
    // the observe-table (presence-feature + scene-features + fused-observation). present
    // + where are native here; who/what un-witnessed on a camera-only frame.
    @Volatile private var lastObs: FkwuSense.Observation? = null
    private val gridN = 4             // 4x4 downsampled luminance grid the camera-eye feeds fkwu

    // Cross-device live loop — the keystone. The phone exchanges its reading with the
    // Mac relay over `adb reverse tcp:8777` every few seconds, then feeds the COMBINED
    // (this device + the nearest other) readings into native fkwu for the cross-device
    // fused observation and the cross-device SURPRISE (how much the two views disagree).
    private val exchangeEveryMs = 3000L
    @Volatile private var lastCrossSurprise = -1
    @Volatile private var crossSurpriseFell = false
    private val crossThread = HandlerThread("fkwu-mesh").also { it.start() }
    private val crossHandler = Handler(crossThread.looper)
    private val crossRunnable = object : Runnable {
        override fun run() {
            if (!stopped) doExchange()
            crossHandler.postDelayed(this, exchangeEveryMs)
        }
    }

    private val clock = SimpleDateFormat("HH:mm:ss", Locale.US)

    // Camera self-heal (PRESERVED): when another app grabs the camera, the eye closes
    // cleanly and re-acquires on a short backoff. The body must not die.
    @Volatile private var recovering = false
    @Volatile private var stopped = false
    private var retryAttempt = 0
    private val maxRetryDelayMs = 4000L
    private val retryRunnable = Runnable { startCamera() }

    private fun sp(v: Float) = TypedValue.COMPLEX_UNIT_SP to v

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0B0E14"))
            setPadding(36, 36, 36, 36)
        }

        val title = TextView(this).apply {
            text = "fkwu — native sense on metal"
            setTextColor(Color.parseColor("#7FB6FF"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            gravity = Gravity.CENTER
        }

        // 1. SPEAKING TOGGLE — host TTS reads the body's verdicts aloud on a rhythm.
        val switchRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(0, 24, 0, 16)
        }
        val switchLabel = TextView(this).apply {
            text = "speak the sensing"
            setTextColor(Color.parseColor("#C9D4E5"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            setPadding(0, 0, 24, 0)
        }
        speakSwitch = Switch(this).apply {
            isChecked = false
            setOnCheckedChangeListener { _, on ->
                speaking = on
                if (on) speak("Speaking on. " + summarySentence(), flush = true)
            }
        }
        switchRow.addView(switchLabel)
        switchRow.addView(speakSwitch)

        headline = TextView(this).apply {
            text = "warming the eye…"
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 34f)
            setTypeface(Typeface.DEFAULT_BOLD)
            gravity = Gravity.CENTER
            setPadding(0, 12, 0, 8)
        }
        detail = TextView(this).apply {
            text = "the verdict below is computed by fkwu on this phone"
            setTextColor(Color.parseColor("#C9D4E5"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
            gravity = Gravity.CENTER
        }

        // 2. WHAT IS BEING SENSED — the live readings block.
        val sensedTitle = sectionLabel("— what is being sensed —")
        sensedBlock = TextView(this).apply {
            text = "presence: …\nluminance: …"
            setTextColor(Color.parseColor("#E2E9F4"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            gravity = Gravity.START
            setPadding(8, 8, 8, 8)
        }

        // 2b. OTHER CELLS — the cross-device roster + native fused/surprise (the keystone).
        val otherTitle = sectionLabel("— other cells (cross-device) —")
        otherCells = TextView(this).apply {
            text = "OTHER CELLS: …\n(reach the Mac relay via: adb reverse tcp:8777 tcp:8777)"
            setTextColor(Color.parseColor("#B9A6FF"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 14f)
            gravity = Gravity.START
            setPadding(8, 8, 8, 8)
        }

        // 4. INQUIRY-PLANE PROBES — the seven inquiry-planes as six probing paths.
        val planesTitle = sectionLabel("— inquiry-plane probes —")
        val planeRow1 = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        val planeRow2 = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        listOf("WHAT", "WHEN", "WHERE").forEach { planeRow1.addView(planeButton(it)) }
        listOf("HOW", "WHO", "WHY").forEach { planeRow2.addView(planeButton(it)) }
        planeReading = TextView(this).apply {
            text = "tap a plane to probe its current reading"
            setTextColor(Color.parseColor("#B7E3C9"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            gravity = Gravity.START
            setPadding(8, 12, 8, 8)
        }

        // 3. SURPRISE EVENTS — the scrolling log.
        val surpriseTitle = sectionLabel("— surprise events —")
        surpriseLog = TextView(this).apply {
            text = "(quiet — no surprise spikes yet)"
            setTextColor(Color.parseColor("#F2C879"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            setPadding(8, 8, 8, 8)
        }
        surpriseScroll = ScrollView(this).apply {
            addView(surpriseLog)
        }

        proof = TextView(this).apply {
            text = ""
            setTextColor(Color.parseColor("#6B7689"))
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 12f)
            gravity = Gravity.START
            setPadding(8, 20, 8, 0)
        }

        root.addView(title, wrap())
        root.addView(switchRow, wrap())
        root.addView(headline, wrap())
        root.addView(detail, wrap())
        root.addView(sensedTitle, wrap())
        root.addView(sensedBlock, wrap())
        root.addView(otherTitle, wrap())
        root.addView(otherCells, wrap())
        root.addView(planesTitle, wrap())
        root.addView(planeRow1, wrap())
        root.addView(planeRow2, wrap())
        root.addView(planeReading, wrap())
        root.addView(surpriseTitle, wrap())
        root.addView(surpriseScroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 220))
        root.addView(proof, wrap())

        val scrollRoot = ScrollView(this).apply { addView(root) }
        setContentView(scrollRoot)

        // The voice carrier (host TTS — native voice is the bring-home). Sensing
        // continues with the switch off; TTS only fires when speaking is ON.
        tts = TextToSpeech(this) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (ttsReady) tts?.language = Locale.US
        }

        if (!FkwuSense.available(this)) {
            headline.text = "fkwu missing"
            detail.text = "the native binary was not packaged into nativeLibraryDir"
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.CAMERA), 42)
        }
    }

    private fun wrap() = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT,
    )

    private fun sectionLabel(text: String) = TextView(this).apply {
        this.text = text
        setTextColor(Color.parseColor("#5E84C9"))
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        gravity = Gravity.CENTER
        setPadding(0, 28, 0, 4)
    }

    private fun planeButton(plane: String) = Button(this).apply {
        text = plane
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        setTextColor(Color.parseColor("#0B0E14"))
        setBackgroundColor(Color.parseColor("#7FB6FF"))
        val lp = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        lp.setMargins(6, 6, 6, 6)
        layoutParams = lp
        setOnClickListener { probePlane(plane) }
    }

    // The seven inquiry-planes as probing paths. Each reports the CURRENT reading from the
    // fused observation fkwu computed over the live grid. present + where are native here;
    // who/what are un-witnessed (no organ on a camera-only frame) — named so, never faked.
    private fun probePlane(plane: String) {
        val now = clock.format(Date())
        val obs = lastObs
        val reading = when (plane) {
            "WHEN" ->
                "WHEN · $now\n(host clock — a native time carrier is a separate organ)"
            "WHERE" ->
                if (obs != null)
                    "WHERE · ${placeName(obs.fusedWhere)} · ${obs.whereCount} place(s) located\n" +
                        "(native fkwu · sf-objects → fo-fuse over the luminance grid)"
                else "WHERE · sensing not started yet"
            "WHAT" ->
                if (obs != null)
                    "WHAT · ${if (obs.whereCount > 0) "${obs.whereCount} object block(s), nearest ${placeName(obs.whereFirst)}" else "uniform field, no object"}\n" +
                        "(native fkwu · sf-objects detail bands over the grid)"
                else "WHAT · sensing not started yet"
            "WHO" ->
                "WHO · un-witnessed\n(identity needs a face-match organ this camera-only frame does not carry)"
            "HOW" ->
                if (obs != null)
                    "HOW · spatial occupancy ${obs.occupancy} → pf-present? ${if (obs.present) "1" else "0"}\n" +
                        "(native fkwu · region-variance over the ${gridN}×${gridN} luminance grid)"
                else "HOW · sensing not started yet"
            "WHY" ->
                "WHY · un-witnessed\n(intent/causal plane needs a reading no single frame carries)"
            else -> "$plane · —"
        }
        planeReading.text = reading
        if (speaking) speak("$plane. " + reading.substringBefore("\n"), flush = true)
    }

    private fun lumaContext(luma: Int): String = when {
        luma < 25 -> "dark"
        luma < 60 -> "dim"
        luma < 140 -> "lit"
        else -> "bright"
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 42 && grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            headline.text = "camera held"
            detail.text = "grant the camera to let fkwu sense the room"
        }
    }

    private fun startCamera() {
        if (stopped) return
        releaseCamera()
        val cm = getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val camId = try { cm.cameraIdList.firstOrNull() } catch (e: Exception) { null } ?: run {
            ui.post { headline.text = "no camera" }
            return
        }
        if (cameraThread == null) {
            cameraThread = HandlerThread("fkwu-eye").also { it.start() }
            cameraHandler = Handler(cameraThread!!.looper)
        }
        reader = ImageReader.newInstance(160, 120, android.graphics.ImageFormat.YUV_420_888, 2).apply {
            setOnImageAvailableListener({ r ->
                val image = r.acquireLatestImage() ?: return@setOnImageAvailableListener
                try {
                    val y = image.planes[0].buffer
                    val stride = image.planes[0].rowStride
                    val luma = averageLuma(y, stride, image.width, image.height)
                    // The downsampled NxN luminance grid the camera-eye hands fkwu: each cell is
                    // the mean luminance of one NxN block of the frame. fkwu reads the SPATIAL
                    // signature (occupancy variance, object detail) — far richer than one average.
                    val grid = lumaGrid(y, stride, image.width, image.height, gridN)
                    onLuma(luma, grid)
                } finally {
                    image.close()
                }
            }, cameraHandler)
        }
        try {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED
            ) return
            cm.openCamera(camId, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    device = camera
                    recovering = false
                    retryAttempt = 0
                    ui.post { headline.text = "warming the eye…" }
                    val surface = reader!!.surface
                    camera.createCaptureSession(listOf(surface), object : CameraCaptureSession.StateCallback() {
                        override fun onConfigured(s: CameraCaptureSession) {
                            session = s
                            try {
                                val req = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply {
                                    addTarget(surface)
                                }
                                s.setRepeatingRequest(req.build(), null, cameraHandler)
                            } catch (e: Exception) {
                                scheduleReacquire("camera lost during configure")
                            }
                        }
                        override fun onConfigureFailed(s: CameraCaptureSession) {
                            scheduleReacquire("camera config failed")
                        }
                    }, cameraHandler)
                }
                override fun onDisconnected(camera: CameraDevice) {
                    scheduleReacquire("camera released to another app")
                }
                override fun onError(camera: CameraDevice, error: Int) {
                    scheduleReacquire("camera busy (err $error)")
                }
            }, cameraHandler)
        } catch (e: Exception) {
            scheduleReacquire("camera open failed: ${e.message}")
        }
    }

    private fun scheduleReacquire(reason: String) {
        if (stopped) return
        releaseCamera()
        recovering = true
        retryAttempt++
        val delay = minOf(1000L * retryAttempt, maxRetryDelayMs)
        ui.post {
            headline.text = "camera busy — reacquiring…"
            headline.setTextColor(Color.parseColor("#F2C879"))
            detail.text = reason
            proof.text = "the eye was taken; fkwu waits and re-grabs (try $retryAttempt)"
        }
        ui.removeCallbacks(retryRunnable)
        ui.postDelayed(retryRunnable, delay)
    }

    private fun releaseCamera() {
        try { session?.close() } catch (_: Exception) {}
        try { device?.close() } catch (_: Exception) {}
        try { reader?.close() } catch (_: Exception) {}
        session = null
        device = null
        reader = null
    }

    private fun averageLuma(y: ByteBuffer, rowStride: Int, w: Int, h: Int): Int {
        var sum = 0L
        var count = 0L
        val step = 4
        var row = 0
        while (row < h) {
            var col = 0
            while (col < w) {
                sum += (y.get(row * rowStride + col).toInt() and 0xFF)
                count++
                col += step
            }
            row += step
        }
        return if (count == 0L) 0 else (sum / count).toInt()
    }

    // Downsample the Y plane to an NxN row-major grid: cell (gx,gy) is the mean luminance
    // of its frame block. This is the carrier shape every sense recipe reads — fkwu does the
    // spatial sensing (variance/occupancy/object-detail) over it, Kotlin only averages blocks.
    private fun lumaGrid(y: ByteBuffer, rowStride: Int, w: Int, h: Int, n: Int): IntArray {
        val grid = IntArray(n * n)
        val bw = w / n
        val bh = h / n
        for (gy in 0 until n) {
            for (gx in 0 until n) {
                var sum = 0L
                var count = 0L
                var row = gy * bh
                val rowEnd = if (gy == n - 1) h else (gy + 1) * bh
                val colStart = gx * bw
                val colEnd = if (gx == n - 1) w else (gx + 1) * bw
                val rstep = maxOf(1, bh / 8)
                val cstep = maxOf(1, bw / 8)
                while (row < rowEnd) {
                    var col = colStart
                    while (col < colEnd) {
                        sum += (y.get(row * rowStride + col).toInt() and 0xFF)
                        count++
                        col += cstep
                    }
                    row += rstep
                }
                grid[gy * n + gx] = if (count == 0L) 0 else (sum / count).toInt()
            }
        }
        return grid
    }

    // Hand the luminance + grid to fkwu ~3x/sec; fkwu runs the fused observation (presence
    // from spatial occupancy, where from object detail) AND the surprise decision; draw both.
    private fun onLuma(luma: Int, grid: IntArray) {
        val now = System.currentTimeMillis()
        if (senseInFlight || now - lastSenseAt < 300) return
        lastSenseAt = now
        senseInFlight = true
        val prev = lastLuma
        cameraHandler?.post {
            // The RICH fused observation over the live grid: present / occupancy / where, all
            // computed natively by fkwu through the observe-table. This is the presence verdict.
            val obs = FkwuSense.observe(this, grid, gridN)
            // Frame-to-frame |Δluma| is the measured byte; fkwu owns the crossing decision.
            val delta = if (prev < 0) 0 else kotlin.math.abs(luma - prev)
            val surprise = if (prev < 0) null else FkwuSense.senseSurprise(this, delta, attend)
            ui.post {
                renderVerdict(luma, obs, delta, surprise)
                senseInFlight = false
            }
        }
    }

    // Name the place from the fused where-plane: the coarse-block id (0..3, raster TL/TR/BL/BR)
    // fkwu's scene read located the nearest thing in. -1 = nowhere placed (an empty frame).
    private fun placeName(blockId: Int): String = when (blockId) {
        0 -> "upper-left"
        1 -> "upper-right"
        2 -> "lower-left"
        3 -> "lower-right"
        else -> "nowhere"
    }

    private fun renderVerdict(luma: Int, obs: FkwuSense.Observation, delta: Int, s: FkwuSense.Verdict?) {
        prevLuma = lastLuma
        lastLuma = luma

        if (!obs.native) {
            headline.text = "fkwu unreachable"
            headline.setTextColor(Color.parseColor("#FF7B7B"))
            detail.text = obs.error ?: "no observation"
            proof.text = "observe-table (live-observe-cli)"
            presenceNative = false
            return
        }
        val present = obs.present
        lastPresent = present
        lastObs = obs
        presenceNative = true
        headline.text = if (present) "PRESENCE: yes" else "PRESENCE: no"
        headline.setTextColor(if (present) Color.parseColor("#5BE3A7") else Color.parseColor("#8896AC"))
        detail.text = "occupancy: ${obs.occupancy}   (native fkwu · pf-occupancy)"

        // fkwu's surprise verdict — append an event when it says the Δ crossed attend.
        val surprised = s?.native == true && s.value == 1L
        if (surprised) {
            surpriseCount++
            appendSurprise(delta)
            lastSurprise = delta
            // Immediate spoken surprise spike when speaking is ON.
            if (speaking) speak("Surprise. Delta $delta.", flush = true)
        }

        val where = if (obs.whereFirst >= 0)
            "${placeName(obs.whereFirst)} (${obs.whereCount} placed)" else "nowhere placed"

        // WHAT IS BEING SENSED — every value here is computed by fkwu over the live grid through
        // the observe-table. who/what have no organ on a camera-only frame: named un-witnessed.
        sensedBlock.text = buildString {
            append("presence:  ${if (present) "yes" else "no"}   (native fkwu · pf-present?)\n")
            append("occupancy: ${obs.occupancy}  ·  ${lumaContext(luma)}   (native · pf-occupancy)\n")
            append("surprise:  Δ$delta vs attend $attend  ·  ${if (surprised) "ATTEND" else "calm"}   (native fkwu)\n")
            append("where:     $where   (native fkwu · sf-objects → fo-fuse)\n")
            append("who:       un-witnessed (no face organ on a camera-only frame)\n")
            append("what:      un-witnessed (no microphone organ this frame)")
        }

        proof.text = buildString {
            append("native fkwu observation: ${obs.raw}   ·   present occupancy where-count where-first fused-where\n")
            append("recipe: live-observe (pf-present? · sf-objects · fo-fuse) — four-way 127, native on metal\n")
            if (s != null) append("native fkwu surprise verdict: ${s.raw}   ·   Form: ${s.expr}\n")
            append("body: C-bootstrap fkwu on Galaxy S23 Ultra · no go/rust/clang/python")
        }

        maybeSpeakRhythm()
    }

    // The cross-device live loop (runs on the mesh thread every exchangeEveryMs).
    // EXCHANGE: POST this device's current native reading to the Mac relay over the
    // adb-reverse tunnel and GET the OTHER cells' readings. FUSE: feed this device's
    // luma/presence + the nearest other cell's into native fkwu for the cross-device
    // fused observation and the cross-device SURPRISE. LEARN: track whether that
    // surprise FELL since last exchange (the trust-climb across real devices).
    private fun doExchange() {
        if (lastLuma < 0) return  // nothing real to share yet
        val ex = FieldRelay.exchange(this, lastPresent, lastLuma, lastSurprise)
        if (!ex.reached) {
            ui.post {
                otherCells.text = "OTHER CELLS: relay unreachable\n" +
                    "(${ex.error ?: "no response"} — run: adb reverse tcp:8777 tcp:8777)"
                otherCells.setTextColor(Color.parseColor("#FF9B8A"))
            }
            return
        }
        if (ex.others.isEmpty()) {
            ui.post {
                otherCells.text = "OTHER CELLS: none yet\n" +
                    "(relay reached — sharing as ${FieldRelay.deviceId(this)}; " +
                    "waiting for the Mac to POST)"
                otherCells.setTextColor(Color.parseColor("#B9A6FF"))
            }
            return
        }
        // The nearest other cell (freshest reading) is the one we fuse with.
        val other = ex.others.minByOrNull { it.ageMs } ?: return
        // NATIVE fkwu: cross-device fused observation + cross-device surprise + trust.
        val fused = FkwuSense.fusedPresence(this, lastPresent, other.present)
        val xSurprise = FkwuSense.crossDeviceSurprise(this, lastLuma, other.luma)
        val xVal = xSurprise.value?.toInt() ?: -1
        val trust = if (xVal >= 0) FkwuSense.trustClimb(this, xVal, attend) else null

        val fell = lastCrossSurprise in 0 until Int.MAX_VALUE &&
            xVal in 0 until lastCrossSurprise
        if (xVal >= 0) {
            crossSurpriseFell = fell
            lastCrossSurprise = xVal
        }

        ui.post {
            val rosterLines = ex.others.joinToString("\n") { o ->
                "  ${o.device}: presence ${if (o.present) "yes" else "no"} · " +
                    "luma ${o.luma} · surprise ${o.surprise} · ${o.ageMs}ms ago"
            }
            val fusedTxt = if (fused.native && fused.value != null)
                (if (fused.value == 1L) "yes" else "no") + "  (native fkwu)"
            else "unreachable"
            val xTxt = if (xSurprise.native && xVal >= 0)
                "$xVal  (native fkwu: |${lastLuma}-${other.luma}|)" else "unreachable"
            val trustTxt = when {
                trust?.native != true || trust.value == null -> "—"
                trust.value == 1L -> "still disagree (surprise ≥ attend $attend)"
                else -> "CONVERGED (surprise < attend $attend) — trust climbed"
            }
            val fellTxt = when {
                lastCrossSurprise < 0 -> "first exchange"
                crossSurpriseFell -> "↓ FELL (was higher last exchange)"
                else -> "steady/rose"
            }
            otherCells.text = buildString {
                append("OTHER CELLS (this device = ${FieldRelay.deviceId(this@LiveSenseActivity)}):\n")
                append(rosterLines).append("\n")
                append("— cross-device fusion (native fkwu) —\n")
                append("fused presence:    $fusedTxt\n")
                append("cross-dev surprise: $xTxt\n")
                append("trust-climb:       $trustTxt\n")
                append("convergence:       $fellTxt")
            }
            otherCells.setTextColor(Color.parseColor("#B9A6FF"))
            if (speaking && xVal >= 0) {
                speak("Cross device surprise $xVal.", flush = false)
            }
        }
    }

    private fun appendSurprise(delta: Int) {
        val line = "surprise $surpriseCount — ${clock.format(Date())}   (Δ$delta)"
        val cur = surpriseLog.text.toString()
        surpriseLog.text = if (cur.startsWith("(quiet")) line else "$cur\n$line"
        surpriseScroll.post { surpriseScroll.fullScroll(View.FOCUS_DOWN) }
    }

    // The spoken summary — built ONLY from the body's current native readings.
    private fun summarySentence(): String {
        if (!presenceNative || lastLuma < 0) return "Sensing not started."
        val pres = if (lastPresent) "Presence yes." else "Presence no."
        val surp = if (lastSurprise >= attend) "Surprise high." else "Surprise low."
        return "$pres $surp"
    }

    private fun maybeSpeakRhythm() {
        if (!speaking) return
        val now = System.currentTimeMillis()
        if (now - lastSpokeAt < speakEveryMs) return
        speak(summarySentence(), flush = false)
    }

    private fun speak(text: String, flush: Boolean) {
        if (!ttsReady) return
        lastSpokeAt = System.currentTimeMillis()
        tts?.speak(
            text,
            if (flush) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD,
            null,
            "sense-${lastSpokeAt}",
        )
    }

    override fun onResume() {
        super.onResume()
        stopped = false
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
            == PackageManager.PERMISSION_GRANTED
        ) {
            retryAttempt = 0
            startCamera()
        }
        // Start the cross-device exchange loop (idempotent: clear any pending first).
        crossHandler.removeCallbacks(crossRunnable)
        crossHandler.postDelayed(crossRunnable, exchangeEveryMs)
    }

    override fun onPause() {
        super.onPause()
        stopped = true
        ui.removeCallbacks(retryRunnable)
        crossHandler.removeCallbacks(crossRunnable)
        releaseCamera()
    }

    override fun onDestroy() {
        super.onDestroy()
        stopped = true
        ui.removeCallbacks(retryRunnable)
        crossHandler.removeCallbacks(crossRunnable)
        crossThread.quitSafely()
        releaseCamera()
        cameraThread?.quitSafely()
        cameraThread = null
        cameraHandler = null
        try { tts?.stop(); tts?.shutdown() } catch (_: Exception) {}
        tts = null
    }
}

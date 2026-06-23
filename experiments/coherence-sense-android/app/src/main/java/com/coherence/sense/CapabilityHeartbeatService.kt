package com.coherence.sense

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import androidx.core.app.NotificationCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.OutputStreamWriter
import java.io.Writer
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

class CapabilityHeartbeatService : Service() {
    private val channelId = "coherence_sense_capability"
    private val notificationId = 42
    private var worker: HandlerThread? = null
    private var workerHandler: Handler? = null
    private var witnessBase = ""
    private var organId = ""
    private var beat = 0L
    private var running = false

    // Continuous overnight logging — runs in the FOREGROUND SERVICE so it survives screen-off, the
    // single requirement for capturing a night of breathing/motion. Two files on the phone:
    //   sleep-<date>/accel.csv  — linear_acceleration in the exact format breath-rhythm.fk reads
    //   sense-log-<date>.ndjson — every sensor event (motion, light, magnetic), for training tomorrow.
    private var sensors: SensorManager? = null
    private var accelWriter: Writer? = null
    private var fieldWriter: Writer? = null
    private var audioWriter: Writer? = null
    private var audioRecord: AudioRecord? = null
    private var audioThread: Thread? = null
    @Volatile private var audioRunning = false
    @Volatile private var logged = 0L
    private val wallFmt = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)

    private val sensorListener = object : SensorEventListener {
        override fun onSensorChanged(e: SensorEvent) {
            try {
                val nowMs = System.currentTimeMillis()
                val tSec = e.timestamp / 1_000_000_000.0   // device monotonic seconds
                if (e.sensor.type == Sensor.TYPE_LINEAR_ACCELERATION && e.values.size >= 3) {
                    accelWriter?.append(
                        "%.6f,%s,%.5f,%.5f,%.5f\n".format(
                            tSec, wallFmt.format(Date(nowMs)), e.values[0], e.values[1], e.values[2])
                    )
                }
                val o = JSONObject().put("t_ms", nowMs).put("ts", tSec).put("type", e.sensor.type)
                val arr = JSONArray(); for (v in e.values) arr.put(v.toDouble())
                fieldWriter?.append(o.put("v", arr).toString())?.append("\n")
                logged++
            } catch (_: Exception) {}
        }
        override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    }

    private val flushLoop = object : Runnable {
        override fun run() {
            try { accelWriter?.flush(); fieldWriter?.flush(); audioWriter?.flush() } catch (_: Exception) {}
            workerHandler?.postDelayed(this, 5000)
        }
    }

    private fun startLogging() {
        val sm = (getSystemService(Context.SENSOR_SERVICE) as? SensorManager) ?: return
        sensors = sm
        try {
            val date = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
            val dir = File(filesDir, "sleep-$date").apply { mkdirs() }
            val accelFile = File(dir, "accel.csv")
            if (!accelFile.exists() || accelFile.length() == 0L) accelFile.writeText("ts,wall,x,y,z\n")
            accelWriter = java.io.FileWriter(accelFile, true).buffered()   // append
            fieldWriter = java.io.FileWriter(File(filesDir, "sense-log-$date.ndjson"), true).buffered()
        } catch (_: Exception) { return }
        val h = workerHandler
        // 5Hz linear-accel (what breath-rhythm.fk expects) + motion at ~10Hz + ambient at normal.
        sm.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)?.let { sm.registerListener(sensorListener, it, 200_000, h) }
        sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let { sm.registerListener(sensorListener, it, 100_000, h) }
        sm.getDefaultSensor(Sensor.TYPE_GYROSCOPE)?.let { sm.registerListener(sensorListener, it, 100_000, h) }
        sm.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)?.let { sm.registerListener(sensorListener, it, SensorManager.SENSOR_DELAY_NORMAL, h) }
        sm.getDefaultSensor(Sensor.TYPE_LIGHT)?.let { sm.registerListener(sensorListener, it, SensorManager.SENSOR_DELAY_NORMAL, h) }
        h?.postDelayed(flushLoop, 5000)
        startAudioLogging()
    }

    // The always-on ear: one continuous AudioRecord owns the mic and logs the ENERGY ENVELOPE per
    // ~0.5s window (RMS + a 0..9 band) — enough for snoring, surprises, room liveness, and the world
    // model, while raw speech stays OUT of the log. Transcription / music-id come from routing audio to
    // the agent later; on-device they'd need their own mic, which this capture already holds.
    private fun startAudioLogging() {
        if (audioRunning) return
        try {
            val date = SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())
            val af = File(File(filesDir, "sleep-$date").apply { mkdirs() }, "audio.csv")
            if (!af.exists() || af.length() == 0L) af.writeText("t_ms,wall,rms,band\n")
            audioWriter = java.io.FileWriter(af, true).buffered()
            val sr = 16000
            val minBuf = AudioRecord.getMinBufferSize(sr, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val rec = AudioRecord(
                MediaRecorder.AudioSource.MIC, sr,
                AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
                max(minBuf, sr) // ~1s
            )
            if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return }
            audioRecord = rec
            audioRunning = true
            rec.startRecording()
            audioThread = Thread {
                val win = ShortArray(sr / 2)   // 0.5s windows
                while (audioRunning) {
                    val n = rec.read(win, 0, win.size)
                    if (n <= 0) continue
                    var sumSq = 0.0
                    for (i in 0 until n) { val s = win[i].toDouble(); sumSq += s * s }
                    val rms = sqrt(sumSq / n)
                    val band = min(9, max(0, (ln(rms + 1.0) / ln(2.0)).toInt()))  // log2 energy band 0..9
                    val nowMs = System.currentTimeMillis()
                    try { audioWriter?.append("$nowMs,${wallFmt.format(Date(nowMs))},${rms.toInt()},$band\n") } catch (_: Exception) {}
                }
            }.also { it.isDaemon = true; it.start() }
        } catch (_: Exception) { audioRunning = false }
    }

    private fun stopAudioLogging() {
        audioRunning = false
        try { audioThread?.join(800) } catch (_: Exception) {}
        try { audioRecord?.stop(); audioRecord?.release() } catch (_: Exception) {}
        audioRecord = null
        try { audioWriter?.flush(); audioWriter?.close() } catch (_: Exception) {}
    }

    private fun stopLogging() {
        try { sensors?.unregisterListener(sensorListener) } catch (_: Exception) {}
        stopAudioLogging()
        try { accelWriter?.flush(); accelWriter?.close() } catch (_: Exception) {}
        try { fieldWriter?.flush(); fieldWriter?.close() } catch (_: Exception) {}
    }

    override fun onCreate() {
        super.onCreate()
        ensureNotificationChannel()
        val notif = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("Coherence Sense")
            .setContentText("Sensing the field — motion, light, sound")
            .setOngoing(true)
            .build()
        // Android 10+ wants the FGS type at start time; microphone type is required to capture audio.
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(
                notificationId, notif,
                android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC or
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
            )
        } else {
            startForeground(notificationId, notif)
        }
        worker = HandlerThread("coherence-capability-heartbeat").also { it.start() }
        workerHandler = Handler(worker!!.looper)
        workerHandler?.post { startLogging() }   // begin sensor logging immediately, witness or not
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val prefs = getSharedPreferences(PREFS, MODE_PRIVATE)
        organId = intent?.getStringExtra(EXTRA_ORGAN_ID)
            ?: prefs.getString(KEY_ORGAN_ID, null)
            ?: "hati-organ-android-unknown"
        witnessBase = (intent?.getStringExtra(EXTRA_WITNESS_BASE)
            ?: prefs.getString(KEY_WITNESS_BASE, "")
            ?: "").trim().removeSuffix("/")
        if (witnessBase.isBlank()) {
            // No witness to share with, but keep the service ALIVE — logging runs regardless (started
            // in onCreate). The night of data lands on the phone whether or not a witness is reachable.
            return START_STICKY
        }
        prefs.edit()
            .putString(KEY_ORGAN_ID, organId)
            .putString(KEY_WITNESS_BASE, witnessBase)
            .putBoolean(KEY_SHARING_ENABLED, true)
            .apply()
        if (!running) {
            running = true
            workerHandler?.post(heartbeatLoop)
        }
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        stopLogging()
        workerHandler?.removeCallbacksAndMessages(null)
        worker?.quitSafely()
        worker = null
        workerHandler = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private val heartbeatLoop = object : Runnable {
        override fun run() {
            if (!running) return
            sendHeartbeat()
            workerHandler?.postDelayed(this, 2000)
        }
    }

    private fun sendHeartbeat() {
        val base = witnessBase.trim().removeSuffix("/")
        if (base.isBlank()) return
        val payload = JSONObject()
            .put("organ_id", organId)
            .put("capability_heartbeat", capabilityHeartbeat())
            .put("organs_active", JSONArray(activeOrgans()))
            .put("channels_offered", JSONArray(offeredTransports()))
            .put("body_state", bodyState())
            .put("tick", beat++)
        try {
            val conn = (URL("$base/sense").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                connectTimeout = 4000
                readTimeout = 4000
                setRequestProperty("Content-Type", "application/json")
            }
            OutputStreamWriter(conn.outputStream).use { it.write(payload.toString()) }
            conn.responseCode
            conn.disconnect()
        } catch (_: Exception) {
            // The next foreground tick retries; the Mac witness records absence by timeout.
        }
    }

    private fun capabilityHeartbeat(): JSONObject =
        JSONObject()
            .put("kind", "android-capability-heartbeat")
            .put("active", true)
            .put("interval_ms", 2000)
            .put("privacy", "summary-only/no-raw-audio-frame-buffer")

    private fun activeOrgans(): List<String> {
        val organs = mutableListOf("network", "screen")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) organs.add("bluetooth-le")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_MICROPHONE)) organs.add("mic-capable")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)) organs.add("camera-capable")
        return organs.distinct().sorted()
    }

    private fun offeredTransports(): List<String> {
        val transports = mutableListOf("wifi", "screen")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) transports.add("ble")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_MICROPHONE)) transports.add("audio")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)) transports.add("video")
        return transports.distinct().sorted()
    }

    private fun bodyState(): JSONObject =
        JSONObject()
            .put("organs_active", activeOrgans().size)
            .put("present_peers", 1)
            .put("surprise_count", 0)
            .put("error_count", 0)
            .put("sample_count", beat + 1)

    private fun ensureNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            channelId,
            "Coherence Sense capability",
            NotificationManager.IMPORTANCE_LOW,
        )
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(channel)
    }

    companion object {
        const val PREFS = "hati_mesh_identity"
        const val KEY_ORGAN_ID = "organ_id"
        const val KEY_WITNESS_BASE = "witness_base"
        const val KEY_SHARING_ENABLED = "sharing_enabled"
        const val EXTRA_ORGAN_ID = "organ_id"
        const val EXTRA_WITNESS_BASE = "witness_base"
    }
}

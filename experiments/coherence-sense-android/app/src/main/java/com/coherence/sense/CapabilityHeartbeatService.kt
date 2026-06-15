package com.coherence.sense

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import androidx.core.app.NotificationCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class CapabilityHeartbeatService : Service() {
    private val channelId = "coherence_sense_capability"
    private val notificationId = 42
    private var worker: HandlerThread? = null
    private var workerHandler: Handler? = null
    private var witnessBase = ""
    private var organId = ""
    private var beat = 0L
    private var running = false

    override fun onCreate() {
        super.onCreate()
        ensureNotificationChannel()
        startForeground(
            notificationId,
            NotificationCompat.Builder(this, channelId)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("Coherence Sense")
                .setContentText("Capability heartbeat is live")
                .setOngoing(true)
                .build(),
        )
        worker = HandlerThread("coherence-capability-heartbeat").also { it.start() }
        workerHandler = Handler(worker!!.looper)
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
            stopSelf()
            return START_NOT_STICKY
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

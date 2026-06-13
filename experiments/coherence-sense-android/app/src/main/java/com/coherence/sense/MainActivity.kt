package com.coherence.sense

// Coherence Sense — v0. A thin CARRIER: this phone becomes a sense organ of the network.
// It reads the device's senses (accelerometer, gyroscope, light, magnetometer), streams a
// snapshot to the Mac over WiFi, and shows what the Mac witnesses back. The BODY — the proven
// Form recipes that recognize / predict / learn — runs on the Mac (and, in v1, on the kernel
// this app will load natively). Nothing streams unless you connect; the senses are held until then.

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.LocationManager
import android.net.TrafficStats
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.StatFs
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.widget.ImageView
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.appcompat.app.AppCompatActivity
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.UUID

class MainActivity : AppCompatActivity(), SensorEventListener {

    private lateinit var sm: SensorManager
    private val latest = HashMap<Int, FloatArray>()
    private val handler = Handler(Looper.getMainLooper())
    private var connected = false
    private var tick = 0
    private var sentBytes = 0L
    private var sentSamples = 0L
    private var innerCellsCreated = 0L
    private var innerCellsUpdated = 0L
    private var innerCellsFreed = 0L
    private var flowWindowStarted = System.currentTimeMillis()

    private lateinit var feed: TextView
    private lateinit var status: TextView
    private lateinit var identity: TextView
    private lateinit var channels: TextView
    private lateinit var dashboard: TextView
    private lateinit var qr: ImageView
    private lateinit var urlField: EditText
    private lateinit var meshField: EditText
    private lateinit var stewardField: EditText
    private lateinit var connectBtn: Button
    private lateinit var organId: String

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        feed = findViewById(R.id.feedView)
        status = findViewById(R.id.statusView)
        identity = findViewById(R.id.identityView)
        channels = findViewById(R.id.channelsView)
        dashboard = findViewById(R.id.dashboardView)
        qr = findViewById(R.id.qrView)
        urlField = findViewById(R.id.urlField)
        meshField = findViewById(R.id.meshField)
        stewardField = findViewById(R.id.stewardField)
        connectBtn = findViewById(R.id.connectBtn)
        sm = getSystemService(SENSOR_SERVICE) as SensorManager
        organId = loadOrganId()
        identity.text = "organ: $organId\nsteward: unbound"
        renderQr()
        meshField.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = renderQr()
            override fun afterTextChanged(s: Editable?) = Unit
        })
        renderDashboard()
        connectBtn.setOnClickListener { toggle() }
    }

    private fun loadOrganId(): String {
        val prefs = getSharedPreferences("hati_mesh_identity", MODE_PRIVATE)
        val existing = prefs.getString("organ_id", null)
        if (!existing.isNullOrBlank()) return existing
        val androidId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID) ?: UUID.randomUUID().toString()
        val salt = UUID.randomUUID().toString()
        val digest = MessageDigest.getInstance("SHA-256")
            .digest("$packageName:$androidId:$salt".toByteArray())
            .joinToString("") { "%02x".format(it) }
            .take(24)
        val created = "hati-organ-android-$digest"
        prefs.edit().putString("organ_id", created).apply()
        return created
    }

    private fun toggle() {
        connected = !connected
        if (connected) {
            registerSensor(Sensor.TYPE_ACCELEROMETER)
            registerSensor(Sensor.TYPE_GYROSCOPE)
            registerSensor(Sensor.TYPE_LIGHT)
            registerSensor(Sensor.TYPE_MAGNETIC_FIELD)
            requestOptionalPermissions()
            connectBtn.text = "Pause — hold the senses"
            status.text = "connecting to ${urlField.text}…"
            announcePresence()
            handler.post(meshLoop)
            handler.post(loop)
        } else {
            sm.unregisterListener(this)
            handler.removeCallbacks(loop)
            handler.removeCallbacks(meshLoop)
            connectBtn.text = "Connect + share senses"
            status.text = "paused — senses held"
            innerCellsFreed += 1
            renderDashboard()
        }
    }

    private fun requestOptionalPermissions() {
        val missing = listOf(
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA,
        ).filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) ActivityCompat.requestPermissions(this, missing.toTypedArray(), 17)
    }

    private fun registerSensor(type: Int) {
        sm.getDefaultSensor(type)?.let {
            sm.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
    }

    private val loop = object : Runnable {
        override fun run() {
            if (!connected) return
            sendSnapshot()
            handler.postDelayed(this, 700)
        }
    }

    private fun arr(v: FloatArray): JSONArray = JSONArray().apply { put(v[0].toDouble()); put(v[1].toDouble()); put(v[2].toDouble()) }

    private fun sendSnapshot() {
        val base = urlField.text.toString().trim().removeSuffix("/")
        val snap = JSONObject()
        snap.put("organ_id", organId)
        latest[Sensor.TYPE_ACCELEROMETER]?.let { snap.put("accel", arr(it)) }
        latest[Sensor.TYPE_GYROSCOPE]?.let { snap.put("gyro", arr(it)) }
        latest[Sensor.TYPE_LIGHT]?.let { snap.put("light", it[0].toDouble()) }
        latest[Sensor.TYPE_MAGNETIC_FIELD]?.let { snap.put("mag", arr(it)) }
        snap.put("tick", tick++)
        innerCellsCreated += 1

        Thread {
            try {
                val conn = (URL("$base/sense").openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    doOutput = true
                    connectTimeout = 4000
                    readTimeout = 4000
                    setRequestProperty("Content-Type", "application/json")
                }
                val encoded = snap.toString()
                OutputStreamWriter(conn.outputStream).use { it.write(encoded) }
                sentBytes += encoded.toByteArray().size.toLong()
                sentSamples += 1
                val code = conn.responseCode
                val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    ?.bufferedReader()?.readText() ?: ""
                conn.disconnect()
                runOnUiThread { onReply(code, body, snap) }
            } catch (e: Exception) {
                runOnUiThread { status.text = "offline — ${e.message}" }
            }
        }.start()
    }

    private val meshLoop = object : Runnable {
        override fun run() {
            if (!connected) return
            refreshMesh()
            handler.postDelayed(this, 5000)
        }
    }

    private fun announcePresence() {
        val base = meshField.text.toString().trim().removeSuffix("/")
        val payload = JSONObject()
            .put("organ_id", organId)
            .put("organ_kind", "android-phone")
            .put("app", "coherence-sense")
            .put("app_version", "0.2")
            .put("target", "android-arm64")
            .put("steward_cell_id", stewardCellId())
            .put("steward_label", stewardLabel())
            .put(
                "capabilities",
                JSONArray()
                    .put("cap.sensor.read")
                    .put("cap.video.frame")
                    .put("cap.audio.sample")
                    .put("cap.screen.write")
                    .put("cap.http.request")
                    .put("cap.mesh.presence"),
            )
            .put(
                "lanes",
                JSONArray()
                    .put("sensor:signal")
                    .put("video:rgba-time")
                    .put("audio:pcm16")
                    .put("screen:write")
                    .put("hati.mesh:presence"),
            )

        Thread {
            try {
                val conn = (URL("$base/hati/mesh/organs/announce").openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    doOutput = true
                    connectTimeout = 5000
                    readTimeout = 5000
                    setRequestProperty("Content-Type", "application/json")
                }
                OutputStreamWriter(conn.outputStream).use { it.write(payload.toString()) }
                val code = conn.responseCode
                val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    ?.bufferedReader()?.readText() ?: ""
                conn.disconnect()
                runOnUiThread { onAnnounceReply(code, body) }
            } catch (e: Exception) {
                runOnUiThread { identity.text = "organ: $organId\nmesh: offline — ${e.message}" }
            }
        }.start()
    }

    private fun flowRates(): Pair<Double, Double> {
        val elapsed = ((System.currentTimeMillis() - flowWindowStarted).coerceAtLeast(1)).toDouble() / 1000.0
        return Pair(sentSamples.toDouble() / elapsed, sentBytes.toDouble() / elapsed)
    }

    private fun refreshMesh() {
        val base = meshField.text.toString().trim().removeSuffix("/")
        Thread {
            try {
                sendHeartbeat(base)
                val organsConn = (URL("$base/hati/mesh/organs?limit=20").openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 5000
                    readTimeout = 5000
                }
                val organsCode = organsConn.responseCode
                val organsBody = (if (organsCode in 200..299) organsConn.inputStream else organsConn.errorStream)
                    ?.bufferedReader()?.readText() ?: ""
                organsConn.disconnect()
                if (organsCode in 200..299) {
                    val peers = JSONObject(organsBody).optJSONArray("items") ?: JSONArray()
                    for (i in 0 until peers.length()) {
                        val peer = peers.optJSONObject(i) ?: continue
                        val peerId = peer.optString("organ_id")
                        if (peerId.isNotBlank() && peerId != organId) {
                            offerSensorChannel(peerId)
                            break
                        }
                    }
                }

                val channelsConn = (URL("$base/hati/mesh/channels?organ_id=$organId&limit=20").openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 5000
                    readTimeout = 5000
                }
                val channelsCode = channelsConn.responseCode
                val channelsBody = (if (channelsCode in 200..299) channelsConn.inputStream else channelsConn.errorStream)
                    ?.bufferedReader()?.readText() ?: ""
                channelsConn.disconnect()
                runOnUiThread { renderChannels(channelsCode, channelsBody) }
            } catch (e: Exception) {
                runOnUiThread { channels.text = "channels: mesh offline — ${e.message}" }
            }
        }.start()
    }

    private fun stewardInput(): String = stewardField.text.toString().trim()

    private fun stewardCellId(): Any {
        val value = stewardInput()
        return if (value.startsWith("cell:") || value.startsWith("contributor:")) value else JSONObject.NULL
    }

    private fun stewardLabel(): Any {
        val value = stewardInput()
        return if (value.isNotBlank()) value else JSONObject.NULL
    }

    private fun renderQr() {
        val payload = JSONObject()
            .put("mesh", "hati.mesh")
            .put("organ_id", organId)
            .put("offer", "identify-and-open-channel")
            .put("api", meshField.text.toString().trim())
            .toString()
        try {
            val matrix = QRCodeWriter().encode(payload, BarcodeFormat.QR_CODE, 320, 320)
            val bmp = Bitmap.createBitmap(320, 320, Bitmap.Config.ARGB_8888)
            for (x in 0 until 320) {
                for (y in 0 until 320) {
                    bmp.setPixel(x, y, if (matrix[x, y]) Color.BLACK else Color.WHITE)
                }
            }
            qr.setImageBitmap(bmp)
        } catch (_: Exception) {
            qr.setImageBitmap(null)
        }
    }

    private fun permissionState(permission: String): String =
        if (ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED) "granted" else "not-granted"

    private fun gpsState(): String {
        return if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) != PackageManager.PERMISSION_GRANTED
        ) {
            "not-granted"
        } else try {
            val lm = getSystemService(LOCATION_SERVICE) as LocationManager
            val loc = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER)
                ?: lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
            if (loc == null) "granted/no-fix" else "%.5f,%.5f".format(loc.latitude, loc.longitude)
        } catch (_: SecurityException) {
            "not-granted"
        } catch (_: Exception) {
            "unavailable"
        }
    }

    private fun diskState(): String {
        val stat = StatFs(Environment.getDataDirectory().path)
        val freeMb = stat.availableBytes / (1024 * 1024)
        val totalMb = stat.totalBytes / (1024 * 1024)
        return "${freeMb}MB/${totalMb}MB free"
    }

    private fun memoryState(): String {
        val rt = Runtime.getRuntime()
        val usedMb = (rt.totalMemory() - rt.freeMemory()) / (1024 * 1024)
        val maxMb = rt.maxMemory() / (1024 * 1024)
        return "${usedMb}MB/${maxMb}MB used"
    }

    private fun networkState(): String {
        val rx = TrafficStats.getTotalRxBytes()
        val tx = TrafficStats.getTotalTxBytes()
        return if (rx == TrafficStats.UNSUPPORTED.toLong() || tx == TrafficStats.UNSUPPORTED.toLong()) {
            "unavailable"
        } else {
            "rx=${rx / 1024}KB tx=${tx / 1024}KB"
        }
    }

    private fun renderDashboard() {
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        val active = latest.keys.mapNotNull {
            when (it) {
                Sensor.TYPE_ACCELEROMETER -> "motion:accelerometer"
                Sensor.TYPE_GYROSCOPE -> "motion:gyroscope"
                Sensor.TYPE_LIGHT -> "light"
                Sensor.TYPE_MAGNETIC_FIELD -> "magnetometer"
                else -> null
            }
        }.sorted()
        dashboard.text = listOf(
            "floor: active samples are shown; unavailable and not-granted lanes are explicit",
            "north-star: signed organs negotiate any available sound/video/text/screen/camera/network channel",
            "sensed: ${if (active.isEmpty()) "none" else active.joinToString(",")}",
            "gps: ${gpsState()}",
            "mic: ${permissionState(Manifest.permission.RECORD_AUDIO)} / offered-not-sampling",
            "camera: ${permissionState(Manifest.permission.CAMERA)} / offered-not-sampling",
            "screen: active dashboard + QR offer",
            "disk: ${diskState()}",
            "network: ${networkState()}",
            "pressure: cpu cores=${Runtime.getRuntime().availableProcessors()} ram=${memoryState()} gpu=floor:cataloged dsp=floor:cataloged mlx=unsupported-on-android",
            "cells: created=$innerCellsCreated updated=$innerCellsUpdated freed=$innerCellsFreed",
            "flow: sensor %.2f samples/s %.0f B/s".format(samplesPerSecond, bytesPerSecond),
        ).joinToString("\n")
    }

    private fun sendHeartbeat(base: String) {
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        val payload = JSONObject()
            .put("organ_id", organId)
            .put("listening", true)
            .put("active_channels", JSONArray().put("sensor:signal"))
            .put("sample_rate_hz", samplesPerSecond)
            .put("bytes_per_second", bytesPerSecond)
        val conn = (URL("$base/hati/mesh/organs/heartbeat").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            doOutput = true
            connectTimeout = 5000
            readTimeout = 5000
            setRequestProperty("Content-Type", "application/json")
        }
        OutputStreamWriter(conn.outputStream).use { it.write(payload.toString()) }
        conn.responseCode
        conn.disconnect()
    }

    private fun offerSensorChannel(peerId: String) {
        val base = meshField.text.toString().trim().removeSuffix("/")
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        val payload = JSONObject()
            .put("from_organ_id", organId)
            .put("to_organ_id", peerId)
            .put("protocol", "sensor:signal")
            .put("interface", "offer:observe-sensor-field")
            .put("capability", "cap.sensor.read")
            .put("codec", "json")
            .put("status", "offered")
            .put("sample_rate_hz", samplesPerSecond)
            .put("bytes_per_second", bytesPerSecond)
        try {
            val conn = (URL("$base/hati/mesh/channels/offer").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                connectTimeout = 5000
                readTimeout = 5000
                setRequestProperty("Content-Type", "application/json")
            }
            OutputStreamWriter(conn.outputStream).use { it.write(payload.toString()) }
            conn.responseCode
            conn.disconnect()
        } catch (_: Exception) {
            // The next mesh refresh will show offline state.
        }
    }

    private fun renderChannels(code: Int, body: String) {
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        if (code !in 200..299) {
            channels.text = "channels: list failed $code\nsensor flow: %.2f samples/s, %.0f B/s".format(samplesPerSecond, bytesPerSecond)
            return
        }
        val rows = JSONObject(body).optJSONArray("items") ?: JSONArray()
        val lines = mutableListOf("open local flow: sensor:signal %.2f samples/s %.0f B/s".format(samplesPerSecond, bytesPerSecond))
        for (i in 0 until rows.length().coerceAtMost(4)) {
            val row = rows.optJSONObject(i) ?: continue
                lines.add("${row.optString("status")} ${row.optString("protocol")} -> ${row.optString("to_organ_id").takeLast(8)} ${row.optDouble("bytes_per_second", 0.0).toInt()} B/s")
        }
        lines.add("offerable: screen:write audio:pcm16 video:rgba-time")
        channels.text = lines.joinToString("\n")
        renderDashboard()
    }

    private fun onAnnounceReply(code: Int, body: String) {
        if (code !in 200..299) {
            identity.text = "organ: $organId\nmesh: announce failed $code"
            return
        }
        try {
            val r = JSONObject(body)
            val receipt = r.optJSONObject("receipt")
            val receiptId = receipt?.optString("runtime_event_id", "no-receipt") ?: "no-receipt"
            val steward = r.optJSONObject("identity")?.optString("steward_cell_id", "unbound") ?: "unbound"
            identity.text = "organ: $organId\nsteward: $steward\nmesh receipt: $receiptId"
        } catch (e: Exception) {
            identity.text = "organ: $organId\nmesh: announced"
        }
    }

    private fun onReply(code: Int, body: String, snap: JSONObject) {
        if (code !in 200..299) { status.text = "Mac replied $code"; return }
        try {
            val r = JSONObject(body)
            val recog = r.optString("recognized", "—")
            val pred = r.optString("predicted", "—")
            val witnessed = r.optInt("witnessed", -1)
            status.text = "synced ✓  witnessed $witnessed frames"
            val senses = mutableListOf<String>()
            if (snap.has("accel")) senses.add("accel")
            if (snap.has("gyro")) senses.add("gyro")
            if (snap.has("light")) senses.add("light")
            if (snap.has("mag")) senses.add("mag")
            val line = "▸ ${snap.optInt("tick")}  senses[${senses.joinToString(",")}]  field:$recog  next:$pred\n"
            feed.text = (line + feed.text).take(6000)
        } catch (e: Exception) {
            status.text = "synced — ${body.take(80)}"
        }
    }

    override fun onSensorChanged(e: SensorEvent) {
        latest[e.sensor.type] = e.values.clone()
        innerCellsUpdated += 1
        renderDashboard()
    }
    override fun onAccuracyChanged(s: Sensor?, accuracy: Int) {}

    override fun onPause() {
        super.onPause()
        sm.unregisterListener(this)
        handler.removeCallbacks(loop)
    }
}

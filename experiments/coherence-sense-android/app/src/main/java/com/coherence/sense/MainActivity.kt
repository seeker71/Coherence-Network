package com.coherence.sense

// Coherence Sense — v0. A thin CARRIER: this phone becomes a sense organ of the network.
// It reads the device's senses (accelerometer, gyroscope, light, magnetometer), streams a
// snapshot to the Mac over WiFi, and shows what the Mac witnesses back. The BODY — the proven
// Form recipes that recognize / predict / learn — runs on the Mac (and, in v1, on the kernel
// this app will load natively). Nothing streams unless you connect; the senses are held until then.

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.LocationManager
import android.net.TrafficStats
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.StatFs
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.ImageView
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
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
import java.net.URLEncoder
import java.security.MessageDigest
import java.util.Locale
import java.util.UUID
import kotlin.math.sqrt

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
    private var peerCount = 0
    private var connectedChannelCount = 0
    private var offeredChannelCount = 0
    private var bestSharedChannel = "network:http"
    private var meshState = "not announced"
    private var lastMacState = "not connected"
    private var surpriseCount = 0L
    private var inferenceErrorCount = 0L
    private var micRms = 0.0
    private var micSamples = 0L
    private var audioRecord: AudioRecord? = null
    @Volatile private var micLoopRunning = false
    @Volatile private var snapshotInFlight = false
    @Volatile private var meshRefreshInFlight = false
    private var dashboardRenderScheduled = false
    private var resourceCacheAt = 0L
    private var cachedGpsState = "not-granted"
    private var cachedDiskState = "unknown"
    private var cachedNetworkState = "unknown"
    private var cachedBluetoothState = "unknown"
    private var cachedSpeakerState = "unknown"
    private var cachedCameraState = "unknown"

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
    private lateinit var settingsBtn: Button
    private lateinit var settingsPanel: LinearLayout
    private lateinit var meshSummary: TextView
    private lateinit var sensorLane: TextView
    private lateinit var audioLane: TextView
    private lateinit var videoLane: TextView
    private lateinit var networkLane: TextView
    private lateinit var bluetoothLane: TextView
    private lateinit var resourceLane: TextView
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
        settingsBtn = findViewById(R.id.settingsBtn)
        settingsPanel = findViewById(R.id.settingsPanel)
        meshSummary = findViewById(R.id.meshSummaryView)
        sensorLane = findViewById(R.id.sensorLaneView)
        audioLane = findViewById(R.id.audioLaneView)
        videoLane = findViewById(R.id.videoLaneView)
        networkLane = findViewById(R.id.networkLaneView)
        bluetoothLane = findViewById(R.id.bluetoothLaneView)
        resourceLane = findViewById(R.id.resourceLaneView)
        sm = getSystemService(SENSOR_SERVICE) as SensorManager
        organId = loadOrganId()
        renderIdentity("local identity ready")
        renderFirstFrame()
        handler.post {
            renderQr()
            renderDashboard()
        }
        meshField.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                renderQr()
                renderDashboard()
            }
            override fun afterTextChanged(s: Editable?) = Unit
        })
        stewardField.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = renderIdentity(meshState)
            override fun afterTextChanged(s: Editable?) = Unit
        })
        connectBtn.setOnClickListener { toggle() }
        settingsBtn.setOnClickListener {
            settingsPanel.visibility = if (settingsPanel.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }
    }

    private fun renderFirstFrame() {
        meshSummary.text = "state: local identity ready\npresent peers: 0  connected channels: 0  offered: 0\nbest shared carrier: network:http"
        sensorLane.text = "SENSORS\nfloor visible\nmotion waiting\ngps not-granted"
        audioLane.text = "AUDIO\nmic offered\nspeaker visible"
        videoLane.text = "VIDEO\ncamera offered\nscreen QR/write"
        networkLane.text = "NETWORK\nmesh waiting\nflow 0.00/s"
        bluetoothLane.text = "BLUETOOTH\ncarrier visible\nBLE heartbeat buildable"
        resourceLane.text = "BODY STATE\npeers 0\nsamples 0\nfidelity receipt next"
        dashboard.text = "floor: visible local lanes first; north-star: measured, negotiated sense channels"
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
            flowWindowStarted = System.currentTimeMillis()
            registerSensor(Sensor.TYPE_ACCELEROMETER)
            registerSensor(Sensor.TYPE_GYROSCOPE)
            registerSensor(Sensor.TYPE_LIGHT)
            registerSensor(Sensor.TYPE_MAGNETIC_FIELD)
            requestOptionalPermissions()
            startMicSamplingIfAllowed()
            connectBtn.text = "Pause sharing"
            lastMacState = "connecting to ${urlField.text}"
            status.text = "Sharing senses. Mac lane: $lastMacState"
            announcePresence()
            handler.post(meshLoop)
            handler.post(loop)
        } else {
            sm.unregisterListener(this)
            handler.removeCallbacks(loop)
            handler.removeCallbacks(meshLoop)
            stopMicSampling()
            connectBtn.text = "Start sharing"
            lastMacState = "paused"
            status.text = "Paused. Senses held."
            innerCellsFreed += 1
            renderDashboard()
        }
    }

    private fun requestOptionalPermissions() {
        val permissions = mutableListOf(
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.CAMERA,
        )
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        val missing = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
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
        if (snapshotInFlight) return
        snapshotInFlight = true
        val base = urlField.text.toString().trim().removeSuffix("/")
        val snap = JSONObject()
        snap.put("organ_id", organId)
        latest[Sensor.TYPE_ACCELEROMETER]?.let { snap.put("accel", arr(it)) }
        latest[Sensor.TYPE_GYROSCOPE]?.let { snap.put("gyro", arr(it)) }
        latest[Sensor.TYPE_LIGHT]?.let { snap.put("light", it[0].toDouble()) }
        latest[Sensor.TYPE_MAGNETIC_FIELD]?.let { snap.put("mag", arr(it)) }
        if (micSamples > 0) snap.put("mic_rms", micRms)
        snap.put("organs_active", JSONArray(activeOrgans()))
        snap.put("channels_offered", JSONArray(offeredTransports()))
        snap.put("body_state", bodyStateJson())
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
                runOnUiThread {
                    lastMacState = "offline — ${e.message}"
                    status.text = "Mac lane: $lastMacState"
                    requestDashboardRender()
                }
            } finally {
                snapshotInFlight = false
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
                    .put("cap.bluetooth.presence")
                    .put("cap.network.presence")
                    .put("cap.mesh.presence"),
            )
            .put(
                "lanes",
                JSONArray(channelLanes()),
            )
            .put("organs_active", JSONArray(activeOrgans()))
            .put("channels_offered", JSONArray(offeredTransports()))
            .put("heartbeat", heartbeatJson())

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
                runOnUiThread {
                    meshState = "offline — ${e.message}"
                    renderIdentity(meshState)
                    requestDashboardRender()
                }
            }
        }.start()
    }

    private fun flowRates(): Pair<Double, Double> {
        val elapsed = ((System.currentTimeMillis() - flowWindowStarted).coerceAtLeast(1)).toDouble() / 1000.0
        return Pair(sentSamples.toDouble() / elapsed, sentBytes.toDouble() / elapsed)
    }

    private fun refreshMesh() {
        if (meshRefreshInFlight) return
        meshRefreshInFlight = true
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
                    var present = 0
                    var offered = false
                    var chosen = "network:http"
                    for (i in 0 until peers.length()) {
                        val peer = peers.optJSONObject(i) ?: continue
                        val peerId = peer.optString("organ_id")
                        if (peerId.isNotBlank() && peerId != organId) {
                            present += 1
                            chosen = chooseBestSharedChannel(peer)
                            if (!offered) {
                                offerSensorChannel(peerId, chosen)
                                offered = true
                            }
                        }
                    }
                    peerCount = present
                    bestSharedChannel = if (present > 0) chosen else "none yet"
                    meshState = if (present > 0) "mesh present: $present peer(s)" else "mesh quiet: no peers heard"
                } else {
                    meshState = "mesh list failed $organsCode"
                }

                val encodedOrgan = URLEncoder.encode(organId, "UTF-8")
                val channelsConn = (URL("$base/hati/mesh/channels?organ_id=$encodedOrgan&limit=20").openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 5000
                    readTimeout = 5000
                }
                val channelsCode = channelsConn.responseCode
                val channelsBody = (if (channelsCode in 200..299) channelsConn.inputStream else channelsConn.errorStream)
                    ?.bufferedReader()?.readText() ?: ""
                channelsConn.disconnect()
                runOnUiThread {
                    renderIdentity(meshState)
                    renderChannels(channelsCode, channelsBody)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    meshState = "mesh offline — ${e.message}"
                    channels.text = "channels: $meshState"
                    renderIdentity(meshState)
                    requestDashboardRender()
                }
            } finally {
                meshRefreshInFlight = false
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
        Thread {
            try {
                val matrix = QRCodeWriter().encode(payload, BarcodeFormat.QR_CODE, 320, 320)
                val bmp = Bitmap.createBitmap(320, 320, Bitmap.Config.ARGB_8888)
                for (x in 0 until 320) {
                    for (y in 0 until 320) {
                        bmp.setPixel(x, y, if (matrix[x, y]) Color.BLACK else Color.WHITE)
                    }
                }
                runOnUiThread { qr.setImageBitmap(bmp) }
            } catch (_: Exception) {
                runOnUiThread { qr.setImageBitmap(null) }
            }
        }.start()
    }

    private fun permissionState(permission: String): String =
        if (ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED) "granted" else "not-granted"

    private fun requestDashboardRender() {
        if (Looper.myLooper() != Looper.getMainLooper()) {
            handler.post { requestDashboardRender() }
            return
        }
        if (dashboardRenderScheduled) return
        dashboardRenderScheduled = true
        handler.postDelayed({
            dashboardRenderScheduled = false
            renderDashboard()
        }, 300)
    }

    private fun refreshResourceCacheIfStale() {
        val now = System.currentTimeMillis()
        if (now - resourceCacheAt < 2000) return
        resourceCacheAt = now
        cachedGpsState = readGpsState()
        cachedDiskState = readDiskState()
        cachedNetworkState = readNetworkState()
        cachedBluetoothState = readBluetoothState()
        cachedSpeakerState = readSpeakerState()
        cachedCameraState = readCameraState()
    }

    private fun readGpsState(): String {
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

    private fun readDiskState(): String {
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

    private fun readNetworkState(): String {
        val rx = TrafficStats.getTotalRxBytes()
        val tx = TrafficStats.getTotalTxBytes()
        return if (rx == TrafficStats.UNSUPPORTED.toLong() || tx == TrafficStats.UNSUPPORTED.toLong()) {
            "unavailable"
        } else {
            "rx=${rx / 1024}KB tx=${tx / 1024}KB"
        }
    }

    private fun renderIdentity(meshLine: String) {
        val steward = stewardInput().ifBlank { "unbound" }
        identity.text = listOf(
            "organ: ...${organId.takeLast(24)}",
            "steward: $steward",
            "identity: organ id auto; contact opt-in",
            "mesh: $meshLine",
        ).joinToString("\n")
    }

    private fun activeOrgans(): List<String> {
        val organs = mutableListOf("screen", "network")
        latest.keys.forEach {
            when (it) {
                Sensor.TYPE_ACCELEROMETER -> organs.add("accelerometer")
                Sensor.TYPE_GYROSCOPE -> organs.add("gyroscope")
                Sensor.TYPE_LIGHT -> organs.add("light")
                Sensor.TYPE_MAGNETIC_FIELD -> organs.add("magnetometer")
            }
        }
        if (cachedGpsState.contains(",")) organs.add("gps")
        if (micSamples > 0) organs.add("mic")
        return organs.distinct().sorted()
    }

    private fun offeredTransports(): List<String> {
        val transports = mutableListOf("wifi", "screen")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) transports.add("ble")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_MICROPHONE)) transports.add("audio")
        if (packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)) transports.add("video")
        return transports.distinct()
    }

    private fun channelLanes(): List<String> =
        listOf(
            "hati.mesh:presence",
            "sensor:signal",
            "audio:pcm16",
            "video:rgba-time",
            "screen:write",
            "network:http",
            "bluetooth:presence",
        )

    private fun heartbeatJson(): JSONObject =
        JSONObject()
            .put("device", organId)
            .put("organs", JSONArray(activeOrgans()))
            .put("channels", JSONArray(offeredTransports()))
            .put("beat", tick)
            .put("best_shared", bestSharedChannel)

    private fun bodyStateJson(): JSONObject {
        val presentPeers = if (connected) peerCount + 1 else 0
        return JSONObject()
            .put("organs_active", activeOrgans().size)
            .put("present_peers", presentPeers)
            .put("surprise_count", surpriseCount)
            .put("error_count", inferenceErrorCount)
            .put("sample_count", sentSamples + micSamples)
    }

    private fun jsonArrayHas(array: JSONArray?, value: String): Boolean {
        if (array == null) return false
        for (i in 0 until array.length()) {
            if (array.optString(i) == value) return true
        }
        return false
    }

    private fun chooseBestSharedChannel(peer: JSONObject): String {
        val channels = peer.optJSONArray("channels_offered")
            ?: peer.optJSONArray("channels")
            ?: peer.optJSONArray("lanes")
        val priority = listOf("wifi", "network:http", "ble", "audio", "video", "screen")
        for (candidate in priority) {
            if (offeredTransports().contains(candidate) || (candidate == "network:http" && offeredTransports().contains("wifi"))) {
                if (jsonArrayHas(channels, candidate) || jsonArrayHas(channels, "network:http") || jsonArrayHas(channels, "hati.mesh:presence")) {
                    return if (candidate == "wifi") "network:http" else candidate
                }
            }
        }
        return "network:http"
    }

    private fun readBluetoothState(): String {
        if (!packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)) return "unavailable"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED
        ) {
            return "not-granted"
        }
        return try {
            val manager = getSystemService(BLUETOOTH_SERVICE) as BluetoothManager
            val adapter: BluetoothAdapter? = manager.adapter
            when {
                adapter == null -> "unavailable"
                adapter.isEnabled -> "enabled"
                else -> "disabled"
            }
        } catch (_: SecurityException) {
            "not-granted"
        } catch (_: Exception) {
            "unavailable"
        }
    }

    private fun readSpeakerState(): String {
        val audio = getSystemService(AUDIO_SERVICE) as AudioManager
        val output = if (packageManager.hasSystemFeature(PackageManager.FEATURE_AUDIO_OUTPUT)) "output-ready" else "unavailable"
        return "$output mode=${audio.mode}"
    }

    private fun readCameraState(): String {
        val hardware = if (packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)) "available" else "unavailable"
        return "$hardware / ${permissionState(Manifest.permission.CAMERA)} / offered-not-sampling"
    }

    private fun micState(): String {
        val permission = permissionState(Manifest.permission.RECORD_AUDIO)
        return if (micSamples > 0) {
            "$permission / rms=${"%.3f".format(Locale.US, micRms)}"
        } else {
            "$permission / offered-not-sampling"
        }
    }

    private fun startMicSamplingIfAllowed() {
        if (micLoopRunning) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return
        val minBuffer = AudioRecord.getMinBufferSize(
            16000,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuffer <= 0) return
        try {
            val record = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                16000,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                minBuffer,
            )
            if (record.state != AudioRecord.STATE_INITIALIZED) {
                record.release()
                return
            }
            audioRecord = record
            micLoopRunning = true
            Thread {
                val buffer = ShortArray(minBuffer / 2)
                try {
                    record.startRecording()
                    while (micLoopRunning) {
                        val read = record.read(buffer, 0, buffer.size)
                        if (read > 0) {
                            var sum = 0.0
                            for (i in 0 until read) {
                                val sample = buffer[i].toDouble() / Short.MAX_VALUE.toDouble()
                                sum += sample * sample
                            }
                            micRms = sqrt(sum / read.toDouble())
                            micSamples += 1
                            requestDashboardRender()
                        }
                    }
                } catch (_: Exception) {
                    micLoopRunning = false
                } finally {
                    try {
                        record.stop()
                    } catch (_: Exception) {
                    }
                    record.release()
                }
            }.start()
        } catch (_: SecurityException) {
            micLoopRunning = false
        } catch (_: Exception) {
            micLoopRunning = false
        }
    }

    private fun stopMicSampling() {
        micLoopRunning = false
        audioRecord = null
    }

    private fun renderDashboard() {
        refreshResourceCacheIfStale()
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        val active = activeOrgans()
        val bodyState = bodyStateJson()
        val presentPeers = bodyState.optInt("present_peers")
        meshSummary.text = listOf(
            "state: $meshState",
            "present peers: $peerCount  connected channels: $connectedChannelCount  offered: $offeredChannelCount",
            "best shared carrier: $bestSharedChannel",
        ).joinToString("\n")
        sensorLane.text = listOf(
            "SENSORS",
            "organs ${active.size}",
            "motion ${latest.keys.size}/4",
            "gps $cachedGpsState",
        ).joinToString("\n")
        audioLane.text = listOf(
            "AUDIO",
            "mic ${micState()}",
            "speaker $cachedSpeakerState",
        ).joinToString("\n")
        videoLane.text = listOf(
            "VIDEO",
            "camera $cachedCameraState",
            "screen QR/write active",
            "frames offered",
        ).joinToString("\n")
        networkLane.text = listOf(
            "NETWORK",
            cachedNetworkState,
            "mesh $meshState",
            "flow %.2f/s %.0f B/s".format(Locale.US, samplesPerSecond, bytesPerSecond),
        ).joinToString("\n")
        bluetoothLane.text = listOf(
            "BLUETOOTH",
            cachedBluetoothState,
            "BLE heartbeat buildable",
            "carrier visible",
        ).joinToString("\n")
        resourceLane.text = listOf(
            "BODY STATE",
            "peers $presentPeers",
            "surprises $surpriseCount",
            "errors $inferenceErrorCount",
            "samples ${sentSamples + micSamples}",
            "fidelity receipt next",
        ).joinToString("\n")
        dashboard.text = listOf(
            "floor: active samples, silence, unavailable hardware, and not-granted lanes are visible signals",
            "north-star: signed organs negotiate wifi, bluetooth, audio, video, screen, sensor, and network channels by heartbeat, then measure fidelity, confidence, and density",
            "learned from sister work: signals are information, not verdicts; silence is evidence",
            "sense-organ ripening: current app gathers receipts; complete native hearing/seeing remains a measured challenger, not a claim",
            "sensed: ${if (active.isEmpty()) "none" else active.joinToString(",")}",
            "body-state: organs=${bodyState.optInt("organs_active")} peers=${bodyState.optInt("present_peers")} surprises=${bodyState.optLong("surprise_count")} errors=${bodyState.optLong("error_count")} samples=${bodyState.optLong("sample_count")}",
            "identity: organ id automatic; phone/email label remains opt-in until Android consent flow is wired",
            "screen: active dashboard + QR offer; video frames require camera permission and frame session",
            "disk: $cachedDiskState",
            "pressure: cpu cores=${Runtime.getRuntime().availableProcessors()} ram=${memoryState()} gpu=floor:cataloged dsp=floor:cataloged mlx=unsupported-on-android",
            "cells: created=$innerCellsCreated updated=$innerCellsUpdated freed=$innerCellsFreed",
            "flow: sensor %.2f samples/s %.0f B/s".format(Locale.US, samplesPerSecond, bytesPerSecond),
        ).joinToString("\n")
    }

    private fun sendHeartbeat(base: String) {
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        val payload = JSONObject()
            .put("organ_id", organId)
            .put("listening", true)
            .put("active_channels", JSONArray(channelLanes()))
            .put("organs_active", JSONArray(activeOrgans()))
            .put("channels_offered", JSONArray(offeredTransports()))
            .put("heartbeat", heartbeatJson())
            .put("body_state", bodyStateJson())
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

    private fun offerSensorChannel(peerId: String, bestChannel: String) {
        val base = meshField.text.toString().trim().removeSuffix("/")
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        val payload = JSONObject()
            .put("from_organ_id", organId)
            .put("to_organ_id", peerId)
            .put("protocol", bestChannel)
            .put("interface", "offer:open-shared-sense-channel")
            .put("capability", "cap.mesh.presence")
            .put("codec", "heartbeat+json")
            .put("status", "offered")
            .put("lanes", JSONArray(channelLanes()))
            .put("organs_active", JSONArray(activeOrgans()))
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
            offeredChannelCount += 1
        } catch (_: Exception) {
            // The next mesh refresh will show offline state.
        }
    }

    private fun renderChannels(code: Int, body: String) {
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        if (code !in 200..299) {
            channels.text = "channels: list failed $code\nsilence is signal; local lanes remain offered\nsensor flow: %.2f samples/s, %.0f B/s".format(samplesPerSecond, bytesPerSecond)
            requestDashboardRender()
            return
        }
        val rows = JSONObject(body).optJSONArray("items") ?: JSONArray()
        var connectedRows = 0
        val lines = mutableListOf(
            "local heartbeat: ${activeOrgans().size} organ(s), ${channelLanes().size} lane(s)",
            "best shared carrier: $bestSharedChannel",
            "local flow: %.2f samples/s %.0f B/s".format(samplesPerSecond, bytesPerSecond),
        )
        for (i in 0 until rows.length().coerceAtMost(4)) {
            val row = rows.optJSONObject(i) ?: continue
            val status = row.optString("status", "unknown")
            if (status == "connected" || status == "open" || status == "accepted") connectedRows += 1
            lines.add("${status} ${row.optString("protocol", "unknown")} -> ${row.optString("to_organ_id").takeLast(8)} ${row.optDouble("bytes_per_second", 0.0).toInt()} B/s")
        }
        connectedChannelCount = connectedRows
        lines.add("offerable: sensor:signal audio:pcm16 video:rgba-time screen:write bluetooth:presence")
        channels.text = lines.joinToString("\n")
        requestDashboardRender()
    }

    private fun onAnnounceReply(code: Int, body: String) {
        if (code !in 200..299) {
            meshState = "announce failed $code"
            renderIdentity(meshState)
            requestDashboardRender()
            return
        }
        try {
            val r = JSONObject(body)
            val receipt = r.optJSONObject("receipt")
            val receiptId = receipt?.optString("runtime_event_id", "no-receipt") ?: "no-receipt"
            val steward = r.optJSONObject("identity")?.optString("steward_cell_id", "unbound") ?: "unbound"
            meshState = "announced; receipt ${receiptId.takeLast(10)}"
            renderIdentity("$meshState\nsteward: $steward")
        } catch (e: Exception) {
            meshState = "announced"
            renderIdentity(meshState)
        }
        requestDashboardRender()
    }

    private fun onReply(code: Int, body: String, snap: JSONObject) {
        if (code !in 200..299) {
            lastMacState = "Mac replied $code"
            status.text = lastMacState
            inferenceErrorCount += 1
            requestDashboardRender()
            return
        }
        try {
            val r = JSONObject(body)
            val recog = r.optString("recognized", "—")
            val pred = r.optString("predicted", "—")
            val witnessed = r.optInt("witnessed", -1)
            lastMacState = "synced; witnessed $witnessed frame(s)"
            status.text = "Sharing senses. $lastMacState"
            val senses = mutableListOf<String>()
            if (snap.has("accel")) senses.add("accel")
            if (snap.has("gyro")) senses.add("gyro")
            if (snap.has("light")) senses.add("light")
            if (snap.has("mag")) senses.add("mag")
            if (recog == "novel" || recog == "—") surpriseCount += 1
            val line = "tick ${snap.optInt("tick")}  senses[${senses.joinToString(",")}]  field:$recog  next:$pred\n"
            val current = if (feed.text.toString() == "recent witness: none") "" else feed.text.toString()
            feed.text = (line + current).take(6000)
        } catch (e: Exception) {
            lastMacState = "synced — ${body.take(80)}"
            status.text = lastMacState
        }
        requestDashboardRender()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 17 && connected) startMicSamplingIfAllowed()
        resourceCacheAt = 0L
        requestDashboardRender()
    }

    override fun onSensorChanged(e: SensorEvent) {
        latest[e.sensor.type] = e.values.clone()
        innerCellsUpdated += 1
        requestDashboardRender()
    }
    override fun onAccuracyChanged(s: Sensor?, accuracy: Int) {}

    override fun onPause() {
        super.onPause()
        sm.unregisterListener(this)
        handler.removeCallbacks(loop)
        handler.removeCallbacks(meshLoop)
        stopMicSampling()
    }
}

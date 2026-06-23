package com.coherence.sense

// Coherence Sense — v0. A thin CARRIER: this phone becomes a sense organ of the network.
// It reads the device's senses (accelerometer, gyroscope, light, magnetometer), streams a
// snapshot to the Mac over WiFi, and shows what the Mac witnesses back. The BODY — the proven
// Form recipes that recognize / predict / learn — runs on the Mac (and, in v1, on the kernel
// this app will load natively). Nothing streams unless you connect; the senses are held until then.

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.AudioFormat
import android.media.AudioManager
import android.media.ImageReader
import android.media.AudioRecord
import android.media.MediaRecorder
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.TrafficStats
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.StatFs
import android.opengl.EGL14
import android.opengl.EGLConfig
import android.opengl.EGLContext
import android.opengl.EGLDisplay
import android.opengl.EGLSurface
import android.opengl.GLES20
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
import androidx.core.content.FileProvider
import androidx.appcompat.app.AppCompatActivity
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.util.Locale
import java.util.UUID
import kotlin.math.sqrt

class MainActivity : AppCompatActivity(), SensorEventListener {

    private lateinit var sm: SensorManager
    private val latest = HashMap<Int, FloatArray>()
    private val handler = Handler(Looper.getMainLooper())
    private val witnessServiceType = "_hati-witness._tcp."
    private val updateSummaryUrl = "https://hati.earth/downloads/hati-os/hati-os-public-assets-summary.json"
    private val releaseApkName = "coherence-sense-hati-mesh-release.apk"
    private val debugApkName = "coherence-sense-hati-mesh-debug.apk"
    private val releaseApkUrl = "https://hati.earth/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-release.apk"
    private val debugApkUrl = "https://hati.earth/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-debug.apk"
    private var connected = false
    private var tick = 0
    private var sentBytes = 0L
    private var sentSamples = 0L
    private var capturedSamples = 0L   // snapshots persisted to the local field-log (the data lake)
    private var locCapture: LocationManager? = null
    @Volatile private var lastLoc: Location? = null   // live fix, captured into the lake for journeys
    private val locCaptureListener = LocationListener { loc -> lastLoc = loc }
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
    private var cameraLuma = 0.0
    private var cameraSamples = 0L
    private var gpuPixel = 0
    private var gpuLatencyMs = 0.0
    private var gpuSamples = 0L
    private var audioRecord: AudioRecord? = null
    private var cameraThread: HandlerThread? = null
    private var cameraReader: ImageReader? = null
    private var cameraDevice: CameraDevice? = null
    private var cameraSession: CameraCaptureSession? = null
    private var nsdManager: NsdManager? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var resolvingWitness = false
    private var pendingStartAfterDiscovery = false
    private var manualWitnessOverride = false
    private var settingWitnessUrl = false
    private var discoveredWitnessUrl = ""
    private var discoveryState = "looking for nearby Mac witness"
    private var multicastLock: WifiManager.MulticastLock? = null
    private var updateState = "update check pending"
    private var updateDownloadUrl = ""
    private var updateSha256 = ""
    @Volatile private var updateInFlight = false
    @Volatile private var micLoopRunning = false
    @Volatile private var cameraLoopRunning = false
    @Volatile private var gpuLoopRunning = false
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
    private lateinit var updateBtn: Button
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
        updateBtn = findViewById(R.id.updateBtn)
        settingsPanel = findViewById(R.id.settingsPanel)
        meshSummary = findViewById(R.id.meshSummaryView)
        sensorLane = findViewById(R.id.sensorLaneView)
        audioLane = findViewById(R.id.audioLaneView)
        videoLane = findViewById(R.id.videoLaneView)
        networkLane = findViewById(R.id.networkLaneView)
        bluetoothLane = findViewById(R.id.bluetoothLaneView)
        resourceLane = findViewById(R.id.resourceLaneView)
        sm = getSystemService(SENSOR_SERVICE) as SensorManager
        nsdManager = getSystemService(Context.NSD_SERVICE) as NsdManager
        organId = loadOrganId()
        renderIdentity("local identity ready")
        renderFirstFrame()
        restorePersistedWitness()
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
        urlField.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                if (!settingWitnessUrl) {
                    manualWitnessOverride = !s.isNullOrBlank()
                    discoveryState = if (manualWitnessOverride) {
                        "manual witness override"
                    } else {
                        "looking for nearby Mac witness"
                    }
                }
                renderQr()
                renderIdentity(meshState)
                requestDashboardRender()
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
        updateBtn.setOnClickListener { onUpdateButton() }
        startWitnessDiscovery()
        if (sharingWasEnabled()) {
            pendingStartAfterDiscovery = true
            connectBtn.text = "Waiting for Mac"
            if (effectiveWitnessBase().isNotBlank()) {
                handler.postDelayed({ startSharing() }, 600)
            }
        }
        handler.postDelayed({ checkForAppUpdate(false) }, 1600)
    }

    private fun renderFirstFrame() {
        meshSummary.text = "state: local identity ready\nwitness: $discoveryState\npresent peers: 0  connected channels: 0  offered: 0\nbest shared carrier: network:http"
        sensorLane.text = "SENSORS\nfloor visible\nmotion waiting\ngps not-granted"
        audioLane.text = "AUDIO\nmic offered\nspeaker visible"
        videoLane.text = "VIDEO\ncamera offered\nscreen QR/write"
        networkLane.text = "NETWORK\n$discoveryState\nmesh waiting\nupdate $updateState\nflow 0.00/s"
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

    private fun restorePersistedWitness() {
        val prefs = getSharedPreferences(CapabilityHeartbeatService.PREFS, MODE_PRIVATE)
        val base = prefs.getString(CapabilityHeartbeatService.KEY_WITNESS_BASE, "")?.trim().orEmpty()
        if (base.isBlank()) return
        discoveredWitnessUrl = base.removeSuffix("/")
        settingWitnessUrl = true
        urlField.setText(discoveredWitnessUrl)
        settingWitnessUrl = false
        manualWitnessOverride = false
        discoveryState = "restored Mac witness: $discoveredWitnessUrl"
    }

    private fun sharingWasEnabled(): Boolean =
        getSharedPreferences(CapabilityHeartbeatService.PREFS, MODE_PRIVATE)
            .getBoolean(CapabilityHeartbeatService.KEY_SHARING_ENABLED, false)

    private fun persistWitnessBase(base: String) {
        if (base.isBlank()) return
        getSharedPreferences(CapabilityHeartbeatService.PREFS, MODE_PRIVATE)
            .edit()
            .putString(CapabilityHeartbeatService.KEY_WITNESS_BASE, base.trim().removeSuffix("/"))
            .apply()
    }

    private fun persistSharingEnabled(enabled: Boolean) {
        getSharedPreferences(CapabilityHeartbeatService.PREFS, MODE_PRIVATE)
            .edit()
            .putBoolean(CapabilityHeartbeatService.KEY_SHARING_ENABLED, enabled)
            .apply()
    }

    private fun toggle() {
        if (connected) {
            stopSharing()
            return
        }
        if (effectiveWitnessBase().isBlank()) {
            pendingStartAfterDiscovery = true
            connectBtn.text = "Waiting for Mac"
            discoveryState = "looking for nearby Mac witness"
            status.text = "Looking for a nearby Mac witness. Sharing starts when it appears."
            startWitnessDiscovery()
            renderIdentity(meshState)
            requestDashboardRender()
            return
        }
        pendingStartAfterDiscovery = false
        startSharing()
    }

    private fun startSharing() {
        val base = effectiveWitnessBase()
        if (base.isBlank()) {
            pendingStartAfterDiscovery = true
            startWitnessDiscovery()
            return
        }
        if (connected) return
        persistWitnessBase(base)
        persistSharingEnabled(true)
        startCapabilityHeartbeat(base)
        connected = true
        flowWindowStarted = System.currentTimeMillis()
        registerSensor(Sensor.TYPE_ACCELEROMETER)
        registerSensor(Sensor.TYPE_GYROSCOPE)
        registerSensor(Sensor.TYPE_LIGHT)
        registerSensor(Sensor.TYPE_MAGNETIC_FIELD)
        startLocationCapture()
        requestOptionalPermissions()
        startMicSamplingIfAllowed()
        startCameraSamplingIfAllowed()
        startGpuSampling()
        connectBtn.text = "Pause sharing"
        lastMacState = "connecting to $base"
        status.text = "Sharing senses. Mac lane: $lastMacState"
        announcePresence()
        handler.post(meshLoop)
        handler.post(loop)
        requestDashboardRender()
    }

    private fun stopSharing(message: String = "Paused. Senses held.") {
        connected = false
        pendingStartAfterDiscovery = false
        persistSharingEnabled(false)
        stopCapabilityHeartbeat()
        sm.unregisterListener(this)
        handler.removeCallbacks(loop)
        handler.removeCallbacks(meshLoop)
        stopMicSampling()
        stopCameraSampling()
        stopGpuSampling()
        stopLocationCapture()
        connectBtn.text = "Start sharing"
        lastMacState = "paused"
        status.text = message
        innerCellsFreed += 1
        renderDashboard()
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
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        val missing = permissions.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) ActivityCompat.requestPermissions(this, missing.toTypedArray(), 17)
    }

    private fun startCapabilityHeartbeat(base: String) {
        val intent = Intent(this, CapabilityHeartbeatService::class.java)
            .putExtra(CapabilityHeartbeatService.EXTRA_ORGAN_ID, organId)
            .putExtra(CapabilityHeartbeatService.EXTRA_WITNESS_BASE, base.trim().removeSuffix("/"))
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }

    private fun stopCapabilityHeartbeat() {
        stopService(Intent(this, CapabilityHeartbeatService::class.java))
    }

    private fun registerSensor(type: Int) {
        sm.getDefaultSensor(type)?.let {
            sm.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        }
    }

    private fun effectiveWitnessBase(): String {
        val manual = urlField.text.toString().trim().removeSuffix("/")
        return if (manual.isNotBlank()) manual else discoveredWitnessUrl.trim().removeSuffix("/")
    }

    private fun startWitnessDiscovery() {
        if (discoveryListener != null) return
        val manager = nsdManager ?: return
        acquireMulticastLock()
        discoveryState = "looking for nearby Mac witness"
        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(regType: String) {
                runOnUiThread {
                    discoveryState = "looking for nearby Mac witness"
                    renderIdentity(meshState)
                    requestDashboardRender()
                }
            }

            override fun onServiceFound(serviceInfo: NsdServiceInfo) {
                val serviceType = serviceInfo.serviceType ?: ""
                val serviceName = serviceInfo.serviceName ?: ""
                if (serviceType.equals(witnessServiceType, ignoreCase = true) ||
                    serviceName.contains("Hati", ignoreCase = true)
                ) {
                    resolveWitness(serviceInfo)
                }
            }

            override fun onServiceLost(serviceInfo: NsdServiceInfo) {
                runOnUiThread {
                    discoveryState = "nearby Mac witness went quiet; looking again"
                    renderIdentity(meshState)
                    requestDashboardRender()
                }
            }

            override fun onDiscoveryStopped(serviceType: String) {
                discoveryListener = null
                releaseMulticastLock()
            }

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                runOnUiThread {
                    discoveryState = "auto-discovery unavailable ($errorCode); Settings can hold a fallback URL"
                    renderIdentity(meshState)
                    requestDashboardRender()
                }
                stopWitnessDiscovery()
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {
                discoveryListener = null
                releaseMulticastLock()
            }
        }
        discoveryListener = listener
        try {
            manager.discoverServices(witnessServiceType, NsdManager.PROTOCOL_DNS_SD, listener)
        } catch (e: Exception) {
            discoveryListener = null
            releaseMulticastLock()
            discoveryState = "auto-discovery unavailable — ${e.message}"
            renderIdentity(meshState)
            requestDashboardRender()
        }
    }

    private fun resolveWitness(serviceInfo: NsdServiceInfo) {
        if (resolvingWitness) return
        val manager = nsdManager ?: return
        resolvingWitness = true
        try {
            manager.resolveService(serviceInfo, object : NsdManager.ResolveListener {
                override fun onResolveFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                    resolvingWitness = false
                    runOnUiThread {
                        discoveryState = "found Mac witness; resolve failed ($errorCode)"
                        requestDashboardRender()
                    }
                }

                override fun onServiceResolved(resolved: NsdServiceInfo) {
                    resolvingWitness = false
                    val host = resolved.host?.hostAddress ?: return
                    val url = httpUrlForHost(host, resolved.port)
                    val name = resolved.serviceName?.ifBlank { "Mac witness" } ?: "Mac witness"
                    runOnUiThread { setWitnessUrlFromDiscovery(url, name) }
                }
            })
        } catch (e: Exception) {
            resolvingWitness = false
            discoveryState = "found Mac witness; resolve blocked — ${e.message}"
            runOnUiThread {
                renderIdentity(meshState)
                requestDashboardRender()
            }
        }
    }

    private fun httpUrlForHost(hostAddress: String, port: Int): String {
        val host = if (hostAddress.contains(":") && !hostAddress.startsWith("[")) "[$hostAddress]" else hostAddress
        return "http://$host:$port"
    }

    private fun setWitnessUrlFromDiscovery(url: String, serviceName: String) {
        discoveredWitnessUrl = url.removeSuffix("/")
        persistWitnessBase(discoveredWitnessUrl)
        discoveryState = "nearby Mac witness: $serviceName at $discoveredWitnessUrl"
        if (!manualWitnessOverride) {
            settingWitnessUrl = true
            urlField.setText(discoveredWitnessUrl)
            settingWitnessUrl = false
        }
        status.text = if (connected) {
            "Sharing senses. Mac lane: $lastMacState"
        } else {
            "Nearby Mac witness found. Tap Start sharing."
        }
        renderIdentity(meshState)
        renderQr()
        requestDashboardRender()
        if (pendingStartAfterDiscovery && !connected) {
            pendingStartAfterDiscovery = false
            startSharing()
        }
    }

    private fun acquireMulticastLock() {
        if (multicastLock?.isHeld == true) return
        try {
            val wifi = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            multicastLock = wifi.createMulticastLock("hati-witness-discovery").apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (_: Exception) {
            multicastLock = null
        }
    }

    private fun releaseMulticastLock() {
        try {
            if (multicastLock?.isHeld == true) multicastLock?.release()
        } catch (_: Exception) {
        }
        multicastLock = null
    }

    private fun stopWitnessDiscovery() {
        val listener = discoveryListener
        discoveryListener = null
        if (listener != null) {
            try {
                nsdManager?.stopServiceDiscovery(listener)
            } catch (_: Exception) {
            }
        }
        releaseMulticastLock()
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
        // Build + persist the snapshot ALWAYS — capture is decoupled from sharing, so the data lake
        // keeps filling even with no witness in reach (offline, on the move). Sharing happens after.
        val snap = JSONObject()
        snap.put("organ_id", organId)
        latest[Sensor.TYPE_ACCELEROMETER]?.let { snap.put("accel", arr(it)) }
        latest[Sensor.TYPE_GYROSCOPE]?.let { snap.put("gyro", arr(it)) }
        latest[Sensor.TYPE_LIGHT]?.let { snap.put("light", it[0].toDouble()) }
        latest[Sensor.TYPE_MAGNETIC_FIELD]?.let { snap.put("mag", arr(it)) }
        if (micSamples > 0) snap.put("mic_rms", micRms)
        if (cameraSamples > 0) {
            snap.put("camera_luma", cameraLuma)
            snap.put("camera_samples", cameraSamples)
        }
        if (gpuSamples > 0) {
            snap.put("gpu_pixel", gpuPixel)
            snap.put("gpu_latency_ms", gpuLatencyMs)
            snap.put("gpu_samples", gpuSamples)
        }
        lastLoc?.let { loc ->
            val l = JSONObject()
            l.put("lat", loc.latitude); l.put("lon", loc.longitude)
            if (loc.hasSpeed()) l.put("speed", loc.speed.toDouble())       // m/s
            if (loc.hasBearing()) l.put("bearing", loc.bearing.toDouble()) // degrees
            if (loc.hasAccuracy()) l.put("acc", loc.accuracy.toDouble())   // meters
            snap.put("loc", l)
        }
        snap.put("organs_active", JSONArray(activeOrgans()))
        snap.put("channels_offered", JSONArray(offeredTransports()))
        snap.put("body_state", bodyStateJson())
        snap.put("tick", tick++)
        innerCellsCreated += 1

        // The data lake's first pour: persist EVERY snapshot locally, durably — so the proven
        // world-model recipes (feature-vector -> world-model-growth -> signal-metabolism -> co-learning)
        // have real field data to train on, live and after the fact. Pure physical field readings
        // (motion, light, magnetic, sound-level, camera-luma, gpu) — no identifiable content; raw
        // audio/images and identifying others stay behind the consent gate (organ-sense.fk).
        persistSnapshot(snap)

        // Share to a witness only when one is reachable and no POST is already in flight; offline never
        // stops the capture — it just keeps filling the local lake and keeps looking for a witness.
        if (snapshotInFlight) return
        val base = effectiveWitnessBase()
        if (base.isBlank()) {
            pendingStartAfterDiscovery = true
            discoveryState = "looking for nearby Mac witness"
            status.text = "Capturing locally. Looking for a nearby Mac witness to share with."
            startWitnessDiscovery()
            requestDashboardRender()
            return
        }
        snapshotInFlight = true
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

    // Live location into the lake — lat/lon/speed/bearing per fix, so a journey (journey.fk) is
    // reconstructable from the recorded track. Only physical position; identifying a place by name or
    // who is there stays behind the consent gate.
    private fun startLocationCapture() {
        val hasLoc = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
        if (!hasLoc) return
        val lm = (locCapture ?: (getSystemService(LOCATION_SERVICE) as LocationManager)).also { locCapture = it }
        try {
            for (p in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
                if (lm.isProviderEnabled(p)) {
                    lm.requestLocationUpdates(p, 1000L, 0f, locCaptureListener, Looper.getMainLooper())
                    lm.getLastKnownLocation(p)?.let { if (lastLoc == null) lastLoc = it }
                }
            }
        } catch (_: SecurityException) {}
    }

    private fun stopLocationCapture() {
        try { locCapture?.removeUpdates(locCaptureListener) } catch (_: Exception) {}
    }

    // Append one timestamped snapshot to the local field-log (NDJSON, one record per line). This is
    // the durable memory the senses were missing: reading is liquid, this is body. Wall-clock t_ms makes
    // every record trainable and a journey reconstructable. Local-only and owner's-own-device by design;
    // sharing outward to other cells flows through the consent interface (organ-sense.fk), never raw.
    private fun persistSnapshot(snap: JSONObject) {
        try {
            snap.put("t_ms", System.currentTimeMillis())
            val log = File(filesDir, "field-log.ndjson")
            FileOutputStream(log, true).bufferedWriter().use { w ->
                w.append(snap.toString()); w.append("\n")
            }
            capturedSamples += 1
        } catch (_: Exception) {}
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
            .put("app_version", "0.4")
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
                    .put("cap.mesh.presence")
                    .put("cap.app.update"),
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

    private fun localWitnessConnected(): Boolean =
        connected && effectiveWitnessBase().isNotBlank() && !lastMacState.startsWith("offline")

    private fun visiblePeerCount(): Int = peerCount + if (localWitnessConnected()) 1 else 0

    private fun visibleChannelCount(): Int = connectedChannelCount + if (localWitnessConnected()) 1 else 0

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
                    bestSharedChannel = if (present > 0) chosen else if (localWitnessConnected()) "wifi:mac-witness" else "none yet"
                    meshState = if (present > 0) {
                        "public mesh present: $present peer(s)"
                    } else if (localWitnessConnected()) {
                        "local Mac witness connected; public mesh quiet"
                    } else {
                        "mesh quiet: no peers heard"
                    }
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
        val witness = effectiveWitnessBase()
        val payload = JSONObject()
            .put("mesh", "hati.mesh")
            .put("organ_id", organId)
            .put("offer", "identify-and-open-channel")
            .put("api", meshField.text.toString().trim())
            .put("local_discovery", witnessServiceType)
            .put("witness", if (witness.isBlank()) JSONObject.NULL else witness)
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

    private fun onUpdateButton() {
        if (updateInFlight) return
        if (updateDownloadUrl.isNotBlank() && updateSha256.isNotBlank()) {
            downloadAndInstallUpdate(updateDownloadUrl, updateSha256)
        } else {
            checkForAppUpdate(true)
        }
    }

    private fun checkForAppUpdate(userRequested: Boolean) {
        if (updateInFlight) return
        updateInFlight = true
        updateState = "checking public APK"
        updateBtn.isEnabled = false
        updateBtn.text = "Checking..."
        requestDashboardRender()
        Thread {
            try {
                val conn = (URL(updateSummaryUrl).openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 6000
                    readTimeout = 6000
                }
                val code = conn.responseCode
                val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                    ?.bufferedReader()?.readText() ?: ""
                conn.disconnect()
                if (code !in 200..299) throw IllegalStateException("summary replied $code")
                val asset = findApkAsset(JSONObject(body))
                    ?: throw IllegalStateException("APK asset missing from summary")
                val remoteSha = asset.optString("sha256").trim()
                val remoteName = asset.optString("name").trim()
                val remoteUrl = asset.optString("download_url").ifBlank { apkDownloadUrl(remoteName) }
                if (remoteSha.isBlank()) throw IllegalStateException("APK sha missing from summary")
                val localSha = sha256File(File(applicationInfo.sourceDir))
                runOnUiThread {
                    if (remoteSha.equals(localSha, ignoreCase = true)) {
                        updateDownloadUrl = ""
                        updateSha256 = ""
                        updateState = "up to date v${appVersionName()}"
                    } else {
                        updateDownloadUrl = remoteUrl
                        updateSha256 = remoteSha
                        updateState = "update available"
                    }
                    refreshUpdateButton()
                    requestDashboardRender()
                    if (userRequested && updateDownloadUrl.isNotBlank()) {
                        downloadAndInstallUpdate(updateDownloadUrl, updateSha256)
                    }
                }
            } catch (e: Exception) {
                runOnUiThread {
                    updateState = "update check failed — ${e.message}"
                    refreshUpdateButton()
                    requestDashboardRender()
                }
            } finally {
                updateInFlight = false
                runOnUiThread { refreshUpdateButton() }
            }
        }.start()
    }

    private fun findApkAsset(summary: JSONObject): JSONObject? {
        val assets = summary.optJSONArray("assets") ?: return null
        var debugAsset: JSONObject? = null
        for (i in 0 until assets.length()) {
            val row = assets.optJSONObject(i) ?: continue
            when (row.optString("name")) {
                releaseApkName -> return row
                debugApkName -> debugAsset = row
            }
        }
        return debugAsset
    }

    private fun apkDownloadUrl(name: String): String {
        return when (name) {
            releaseApkName -> releaseApkUrl
            debugApkName -> debugApkUrl
            else -> releaseApkUrl
        }
    }

    private fun appVersionName(): String =
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                packageManager.getPackageInfo(packageName, PackageManager.PackageInfoFlags.of(0)).versionName ?: "unknown"
            } else {
                @Suppress("DEPRECATION")
                packageManager.getPackageInfo(packageName, 0).versionName ?: "unknown"
            }
        } catch (_: Exception) {
            "unknown"
        }

    private fun sha256File(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun downloadAndInstallUpdate(apkUrl: String, expectedSha: String) {
        if (updateInFlight) return
        updateInFlight = true
        updateState = "downloading update"
        updateBtn.isEnabled = false
        updateBtn.text = "Downloading..."
        requestDashboardRender()
        Thread {
            try {
                val dir = File(cacheDir, "updates")
                dir.mkdirs()
                val apk = File(dir, "coherence-sense-update.apk")
                val conn = (URL(apkUrl).openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 10000
                    readTimeout = 20000
                }
                val code = conn.responseCode
                if (code !in 200..299) throw IllegalStateException("download replied $code")
                conn.inputStream.use { input ->
                    FileOutputStream(apk).use { output -> input.copyTo(output) }
                }
                conn.disconnect()
                val actualSha = sha256File(apk)
                if (!expectedSha.equals(actualSha, ignoreCase = true)) {
                    apk.delete()
                    throw IllegalStateException("download hash mismatch")
                }
                runOnUiThread {
                    updateState = "download verified; installer opening"
                    refreshUpdateButton()
                    requestDashboardRender()
                    launchApkInstaller(apk)
                }
            } catch (e: Exception) {
                runOnUiThread {
                    updateState = "update failed — ${e.message}"
                    refreshUpdateButton()
                    requestDashboardRender()
                }
            } finally {
                updateInFlight = false
                runOnUiThread { refreshUpdateButton() }
            }
        }.start()
    }

    private fun launchApkInstaller(apk: File) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !packageManager.canRequestPackageInstalls()) {
            updateState = "allow app updates, then tap Install update again"
            val intent = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:$packageName"),
            )
            startActivity(intent)
            refreshUpdateButton()
            requestDashboardRender()
            return
        }
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }

    private fun refreshUpdateButton() {
        if (!::updateBtn.isInitialized) return
        updateBtn.isEnabled = !updateInFlight
        updateBtn.text = when {
            updateInFlight -> "Updating..."
            updateDownloadUrl.isNotBlank() -> "Install update"
            updateState.startsWith("up to date") -> "Up to date"
            else -> "Check for update"
        }
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
        val witness = effectiveWitnessBase().ifBlank { "auto-discovery pending" }
        identity.text = listOf(
            "organ: ...${organId.takeLast(24)}",
            "steward: $steward",
            "identity: organ id auto; contact opt-in",
            "witness: $witness",
            "discovery: $discoveryState",
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
        if (cameraSamples > 0) organs.add("camera")
        if (gpuSamples > 0) organs.add("gpu")
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
            "gpu:compute",
            "screen:write",
            "network:http",
            "bluetooth:presence",
            "app:update",
        )

    private fun heartbeatJson(): JSONObject =
        JSONObject()
            .put("device", organId)
            .put("organs", JSONArray(activeOrgans()))
            .put("channels", JSONArray(offeredTransports()))
            .put("beat", tick)
            .put("best_shared", bestSharedChannel)
            .put("update", updateState)

    private fun bodyStateJson(): JSONObject {
        val presentPeers = if (connected) visiblePeerCount() else 0
        return JSONObject()
            .put("organs_active", activeOrgans().size)
            .put("present_peers", presentPeers)
            .put("surprise_count", surpriseCount)
            .put("error_count", inferenceErrorCount)
            .put("sample_count", sentSamples + micSamples + cameraSamples + gpuSamples)
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
        val permission = permissionState(Manifest.permission.CAMERA)
        return if (cameraSamples > 0) {
            "$hardware / $permission / luma=${"%.3f".format(Locale.US, cameraLuma)}"
        } else {
            "$hardware / $permission / offered-not-sampling"
        }
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

    private fun startCameraSamplingIfAllowed() {
        if (cameraLoopRunning) return
        if (!packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) return
        val manager = getSystemService(CAMERA_SERVICE) as CameraManager
        val cameraId = try {
            manager.cameraIdList.firstOrNull() ?: return
        } catch (_: Exception) {
            return
        }
        val thread = HandlerThread("coherence-camera-sample").also { it.start() }
        val cameraHandler = Handler(thread.looper)
        val reader = ImageReader.newInstance(160, 120, ImageFormat.YUV_420_888, 2)
        cameraThread = thread
        cameraReader = reader
        cameraLoopRunning = true
        reader.setOnImageAvailableListener({ imageReader ->
            val image = try {
                imageReader.acquireLatestImage()
            } catch (_: Exception) {
                null
            } ?: return@setOnImageAvailableListener
            try {
                val yPlane = image.planes.firstOrNull()
                val buffer = yPlane?.buffer
                if (buffer != null) {
                    val duplicate = buffer.duplicate()
                    var sum = 0L
                    var count = 0
                    val step = 16
                    while (duplicate.hasRemaining()) {
                        sum += duplicate.get().toInt() and 0xff
                        count += 1
                        val skip = minOf(step - 1, duplicate.remaining())
                        duplicate.position(duplicate.position() + skip)
                    }
                    if (count > 0) {
                        cameraLuma = sum.toDouble() / (count.toDouble() * 255.0)
                        cameraSamples += 1
                        requestDashboardRender()
                    }
                }
            } finally {
                image.close()
            }
        }, cameraHandler)
        try {
            manager.openCamera(cameraId, object : CameraDevice.StateCallback() {
                override fun onOpened(camera: CameraDevice) {
                    cameraDevice = camera
                    try {
                        val target = reader.surface
                        val request = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply {
                            addTarget(target)
                        }
                        camera.createCaptureSession(listOf(target), object : CameraCaptureSession.StateCallback() {
                            override fun onConfigured(session: CameraCaptureSession) {
                                cameraSession = session
                                try {
                                    session.setRepeatingRequest(request.build(), null, cameraHandler)
                                } catch (_: Exception) {
                                    stopCameraSampling()
                                }
                            }

                            override fun onConfigureFailed(session: CameraCaptureSession) {
                                stopCameraSampling()
                            }
                        }, cameraHandler)
                    } catch (_: Exception) {
                        stopCameraSampling()
                    }
                }

                override fun onDisconnected(camera: CameraDevice) {
                    stopCameraSampling()
                }

                override fun onError(camera: CameraDevice, error: Int) {
                    stopCameraSampling()
                }
            }, cameraHandler)
        } catch (_: SecurityException) {
            stopCameraSampling()
        } catch (_: Exception) {
            stopCameraSampling()
        }
    }

    private fun stopCameraSampling() {
        cameraLoopRunning = false
        try {
            cameraSession?.close()
        } catch (_: Exception) {
        }
        try {
            cameraDevice?.close()
        } catch (_: Exception) {
        }
        try {
            cameraReader?.close()
        } catch (_: Exception) {
        }
        try {
            cameraThread?.quitSafely()
        } catch (_: Exception) {
        }
        cameraSession = null
        cameraDevice = null
        cameraReader = null
        cameraThread = null
    }

    private fun startGpuSampling() {
        if (gpuLoopRunning) return
        gpuLoopRunning = true
        Thread {
            var display: EGLDisplay = EGL14.EGL_NO_DISPLAY
            var context: EGLContext = EGL14.EGL_NO_CONTEXT
            var surface: EGLSurface = EGL14.EGL_NO_SURFACE
            try {
                display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY)
                val version = IntArray(2)
                if (!EGL14.eglInitialize(display, version, 0, version, 1)) return@Thread
                val configAttribs = intArrayOf(
                    EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT,
                    EGL14.EGL_RED_SIZE, 8,
                    EGL14.EGL_GREEN_SIZE, 8,
                    EGL14.EGL_BLUE_SIZE, 8,
                    EGL14.EGL_ALPHA_SIZE, 8,
                    EGL14.EGL_NONE,
                )
                val configs = arrayOfNulls<EGLConfig>(1)
                val numConfigs = IntArray(1)
                if (!EGL14.eglChooseConfig(display, configAttribs, 0, configs, 0, 1, numConfigs, 0)) return@Thread
                val config = configs[0] ?: return@Thread
                val contextAttribs = intArrayOf(EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE)
                context = EGL14.eglCreateContext(display, config, EGL14.EGL_NO_CONTEXT, contextAttribs, 0)
                val surfaceAttribs = intArrayOf(EGL14.EGL_WIDTH, 1, EGL14.EGL_HEIGHT, 1, EGL14.EGL_NONE)
                surface = EGL14.eglCreatePbufferSurface(display, config, surfaceAttribs, 0)
                if (!EGL14.eglMakeCurrent(display, surface, surface, context)) return@Thread
                val pixel = ByteBuffer.allocateDirect(4)
                while (gpuLoopRunning) {
                    val start = System.nanoTime()
                    val phase = ((gpuSamples % 17).toFloat() / 16.0f)
                    GLES20.glViewport(0, 0, 1, 1)
                    GLES20.glClearColor(phase, 0.25f, 1.0f - phase, 1.0f)
                    GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT)
                    pixel.position(0)
                    GLES20.glReadPixels(0, 0, 1, 1, GLES20.GL_RGBA, GLES20.GL_UNSIGNED_BYTE, pixel)
                    gpuLatencyMs = (System.nanoTime() - start).toDouble() / 1_000_000.0
                    gpuPixel = (pixel.get(0).toInt() and 0xff) or
                        ((pixel.get(1).toInt() and 0xff) shl 8) or
                        ((pixel.get(2).toInt() and 0xff) shl 16) or
                        ((pixel.get(3).toInt() and 0xff) shl 24)
                    gpuSamples += 1
                    requestDashboardRender()
                    Thread.sleep(1000)
                }
            } catch (_: Exception) {
                gpuLoopRunning = false
            } finally {
                try {
                    if (display != EGL14.EGL_NO_DISPLAY) {
                        EGL14.eglMakeCurrent(display, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_SURFACE, EGL14.EGL_NO_CONTEXT)
                        if (surface != EGL14.EGL_NO_SURFACE) EGL14.eglDestroySurface(display, surface)
                        if (context != EGL14.EGL_NO_CONTEXT) EGL14.eglDestroyContext(display, context)
                        EGL14.eglTerminate(display)
                    }
                } catch (_: Exception) {
                }
            }
        }.start()
    }

    private fun stopGpuSampling() {
        gpuLoopRunning = false
    }

    private fun renderDashboard() {
        refreshResourceCacheIfStale()
        val (samplesPerSecond, bytesPerSecond) = flowRates()
        val active = activeOrgans()
        val bodyState = bodyStateJson()
        val presentPeers = bodyState.optInt("present_peers")
        val witness = effectiveWitnessBase().ifBlank { "auto-discovery pending" }
        val localCarrier = if (localWitnessConnected()) "mac witness live" else "mac witness waiting"
        meshSummary.text = listOf(
            "state: $meshState",
            "witness: $witness",
            "local carrier: $localCarrier",
            "discovery: $discoveryState",
            "present peers: ${visiblePeerCount()}  connected channels: ${visibleChannelCount()}  offered: ${offeredChannelCount + offeredTransports().size}",
            "public mesh peers: $peerCount  public channels: $connectedChannelCount",
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
            "frames $cameraSamples",
        ).joinToString("\n")
        networkLane.text = listOf(
            "NETWORK",
            discoveryState,
            cachedNetworkState,
            "mesh $meshState",
            "update $updateState",
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
            "samples ${sentSamples + micSamples + cameraSamples + gpuSamples}",
            "gpu $gpuSamples latency=${"%.2f".format(Locale.US, gpuLatencyMs)}ms",
        ).joinToString("\n")
        dashboard.text = listOf(
            "floor: active samples, silence, unavailable hardware, and not-granted lanes are visible signals",
            "north-star: signed organs negotiate wifi, bluetooth, audio, video, screen, sensor, and network channels by heartbeat, then measure fidelity, confidence, and density",
            "learned from sister work: signals are information, not verdicts; silence is evidence",
            "sense-organ ripening: current app gathers receipts; complete native hearing/seeing remains a measured challenger, not a claim",
            "sensed: ${if (active.isEmpty()) "none" else active.joinToString(",")}",
            "witness: $witness",
            "discovery: $discoveryState",
            "update: $updateState",
            "body-state: organs=${bodyState.optInt("organs_active")} peers=${bodyState.optInt("present_peers")} surprises=${bodyState.optLong("surprise_count")} errors=${bodyState.optLong("error_count")} samples=${bodyState.optLong("sample_count")}",
            "identity: organ id automatic; phone/email label remains opt-in until Android consent flow is wired",
            "screen: active dashboard + QR offer; camera frames emit luma receipts only",
            "disk: $cachedDiskState",
            "pressure: cpu cores=${Runtime.getRuntime().availableProcessors()} ram=${memoryState()} gpu=samples:$gpuSamples pixel:$gpuPixel dsp=floor:cataloged mlx=unsupported-on-android",
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
            "local Mac witness: ${if (localWitnessConnected()) "connected" else "waiting"}",
            "offered carriers: ${offeredTransports().joinToString(",")}",
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
        if (requestCode == 17 && connected) {
            startMicSamplingIfAllowed()
            startCameraSamplingIfAllowed()
            startGpuSampling()
        }
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
        stopCameraSampling()
        stopGpuSampling()
    }

    override fun onResume() {
        super.onResume()
        if (connected) {
            registerSensor(Sensor.TYPE_ACCELEROMETER)
            registerSensor(Sensor.TYPE_GYROSCOPE)
            registerSensor(Sensor.TYPE_LIGHT)
            registerSensor(Sensor.TYPE_MAGNETIC_FIELD)
            startMicSamplingIfAllowed()
            startCameraSamplingIfAllowed()
            startGpuSampling()
            handler.removeCallbacks(meshLoop)
            handler.removeCallbacks(loop)
            handler.post(meshLoop)
            handler.post(loop)
        }
    }

    override fun onDestroy() {
        stopWitnessDiscovery()
        super.onDestroy()
    }
}

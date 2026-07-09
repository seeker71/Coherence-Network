package com.coherence.sema.sense

// The phone's own body-sense: motion, light, heading, place, and room loudness — real
// readings from real sensors, held as one observable field. Raw values stay on the
// device; only summaries ever travel (the privacy floor the Android bridge recipes draw).

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.roundToInt
import kotlin.math.sqrt

data class SenseReading(
    val accelMagnitude: Float = 0f,      // m/s² beyond gravity, smoothed
    val moving: Boolean = false,
    val speedMps: Float? = null,         // ground speed from GPS
    val lux: Float? = null,
    val headingDeg: Float? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    val placeName: String? = null,       // reverse-geocoded — the name of where we are
    val soundRms: Int = 0,               // 0..~12000, room loudness
    val micLive: Boolean = false,
) {
    fun lightWord(): String = when {
        lux == null -> "unread"
        lux < 10f -> "dark"
        lux < 200f -> "dim"
        lux < 1000f -> "lit"
        else -> "bright"
    }

    fun speedKmh(): Float? = speedMps?.let { it * 3.6f }

    // Mode of transport, inferred from ground speed (the model will learn finer distinctions —
    // the walk vs the run, the car vs the train — from the whole field over time; for now the
    // honest read is the speed band). Car and train overlap in speed; named by likelihood.
    fun transportWord(): String {
        val s = speedMps
        if (s == null) return if (moving) "moving" else "still"
        val kmh = s * 3.6f
        return when {
            kmh < 1.5f -> "still"
            kmh < 7f -> "walking"
            kmh < 13f -> "running"
            kmh < 28f -> "cycling"
            kmh < 110f -> "driving"
            kmh < 350f -> "on a train"
            else -> "flying"
        }
    }

    fun soundWord(): String = when {
        !micLive -> "unheard (mic off)"
        soundRms < 300 -> "quiet"
        soundRms < 1500 -> "murmuring"
        soundRms < 5000 -> "lively"
        else -> "loud"
    }

    fun headingWord(): String {
        val h = headingDeg ?: return "unread"
        val names = listOf("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")
        return names[(((h + 22.5f) % 360f) / 45f).toInt().coerceIn(0, 7)]
    }
}

class SenseField(private val context: Context) : SensorEventListener {

    private val _reading = MutableStateFlow(SenseReading())
    val reading: StateFlow<SenseReading> = _reading

    private var sensorManager: SensorManager? = null
    private var lastAccel: FloatArray? = null
    private var lastMag: FloatArray? = null
    private var smoothedAccel = 0f
    private var audioJob: Job? = null

    fun start(scope: CoroutineScope) {
        geoScope = scope
        val sm = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
        sensorManager = sm
        listOf(Sensor.TYPE_ACCELEROMETER, Sensor.TYPE_MAGNETIC_FIELD, Sensor.TYPE_LIGHT).forEach { type ->
            sm.getDefaultSensor(type)?.let { sm.registerListener(this, it, SensorManager.SENSOR_DELAY_UI) }
        }
        startLocation()
        // Audio is owned by RoomEars now (one mic → both level and words); SenseField no longer
        // opens the mic itself, so the two never contend for it.
    }

    fun stop() {
        sensorManager?.unregisterListener(this)
        audioJob?.cancel()
        _reading.value = _reading.value.copy(micLive = false)
    }

    override fun onSensorChanged(e: SensorEvent) {
        when (e.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> {
                lastAccel = e.values.clone()
                val mag = sqrt(e.values[0] * e.values[0] + e.values[1] * e.values[1] + e.values[2] * e.values[2])
                val beyondGravity = abs(mag - 9.81f)
                smoothedAccel = smoothedAccel * 0.8f + beyondGravity * 0.2f
                _reading.value = _reading.value.copy(
                    accelMagnitude = smoothedAccel,
                    moving = smoothedAccel > 0.6f,
                )
                recomputeHeading()
            }
            Sensor.TYPE_MAGNETIC_FIELD -> { lastMag = e.values.clone(); recomputeHeading() }
            Sensor.TYPE_LIGHT -> _reading.value = _reading.value.copy(lux = e.values.firstOrNull())
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    private fun recomputeHeading() {
        val a = lastAccel ?: return
        val m = lastMag ?: return
        val r = FloatArray(9)
        if (SensorManager.getRotationMatrix(r, null, a, m)) {
            val orient = FloatArray(3)
            SensorManager.getOrientation(r, orient)
            val az = Math.toDegrees(orient[0].toDouble()).toFloat()
            _reading.value = _reading.value.copy(headingDeg = (az + 360f) % 360f)
        }
    }

    private var geoScope: CoroutineScope? = null
    private var lastGeocodeAt = 0L
    private val locationListener = LocationListener { loc: Location ->
        _reading.value = _reading.value.copy(
            latitude = loc.latitude,
            longitude = loc.longitude,
            speedMps = if (loc.hasSpeed()) loc.speed else _reading.value.speedMps,
        )
        maybeGeocode(loc)
    }

    // Turn the fix into the NAME of a place — a landmark, a street, a locality — the way we'd
    // say where we are, not a coordinate pair. Throttled; runs off the main thread. (The room's
    // own name is learned from listening + seeing; this is the outer place it sits in.)
    private fun maybeGeocode(loc: Location) {
        val now = System.currentTimeMillis()
        if (now - lastGeocodeAt < 60_000L) return
        lastGeocodeAt = now
        val scope = geoScope ?: return
        scope.launch(Dispatchers.IO) {
            try {
                @Suppress("DEPRECATION")
                val hits = android.location.Geocoder(context).getFromLocation(loc.latitude, loc.longitude, 1)
                val a = hits?.firstOrNull() ?: return@launch
                val name = a.featureName?.takeIf { it.isNotBlank() && it != a.thoroughfare }
                    ?: a.thoroughfare ?: a.subLocality ?: a.locality
                val where = listOfNotNull(name, a.locality?.takeIf { it != name })
                    .distinct().joinToString(", ").ifBlank { a.getAddressLine(0) }
                if (!where.isNullOrBlank()) _reading.value = _reading.value.copy(placeName = where)
            } catch (e: Exception) { /* geocoder needs network; place-name stays unread, honestly */ }
        }
    }

    @SuppressLint("MissingPermission")
    private fun startLocation() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) return
        try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
            lm.getProviders(true).forEach { provider ->
                lm.requestLocationUpdates(provider, 30_000L, 25f, locationListener)
                lm.getLastKnownLocation(provider)?.let { locationListener.onLocationChanged(it) }
            }
        } catch (e: Exception) { /* location stays unread — an honest gap, not a failure */ }
    }

    @SuppressLint("MissingPermission")
    private fun startAudio(scope: CoroutineScope) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED
        ) return
        audioJob?.cancel()
        audioJob = scope.launch(Dispatchers.IO) {
            val rate = 16000
            val minBuf = AudioRecord.getMinBufferSize(
                rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
            )
            if (minBuf <= 0) return@launch
            val recorder = try {
                AudioRecord(
                    MediaRecorder.AudioSource.MIC, rate,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2
                )
            } catch (e: Exception) { return@launch }
            if (recorder.state != AudioRecord.STATE_INITIALIZED) { recorder.release(); return@launch }
            val buf = ShortArray(minBuf)
            try {
                recorder.startRecording()
                _reading.value = _reading.value.copy(micLive = true)
                while (isActive) {
                    val n = recorder.read(buf, 0, buf.size)
                    if (n > 0) {
                        var sum = 0.0
                        for (i in 0 until n) sum += buf[i].toDouble() * buf[i].toDouble()
                        val rms = sqrt(sum / n).roundToInt()
                        _reading.value = _reading.value.copy(soundRms = rms)
                    }
                }
            } finally {
                try { recorder.stop() } catch (e: Exception) { }
                recorder.release()
                _reading.value = _reading.value.copy(micLive = false, soundRms = 0)
            }
        }
    }
}

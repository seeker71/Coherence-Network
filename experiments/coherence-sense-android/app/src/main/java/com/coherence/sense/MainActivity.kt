package com.coherence.sense

// Coherence Sense — v0. A thin CARRIER: this phone becomes a sense organ of the network.
// It reads the device's senses (accelerometer, gyroscope, light, magnetometer), streams a
// snapshot to the Mac over WiFi, and shows what the Mac witnesses back. The BODY — the proven
// Form recipes that recognize / predict / learn — runs on the Mac (and, in v1, on the kernel
// this app will load natively). Nothing streams unless you connect; the senses are held until then.

import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : AppCompatActivity(), SensorEventListener {

    private lateinit var sm: SensorManager
    private val latest = HashMap<Int, FloatArray>()
    private val handler = Handler(Looper.getMainLooper())
    private var connected = false
    private var tick = 0

    private lateinit var feed: TextView
    private lateinit var status: TextView
    private lateinit var urlField: EditText
    private lateinit var connectBtn: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        feed = findViewById(R.id.feedView)
        status = findViewById(R.id.statusView)
        urlField = findViewById(R.id.urlField)
        connectBtn = findViewById(R.id.connectBtn)
        sm = getSystemService(SENSOR_SERVICE) as SensorManager
        connectBtn.setOnClickListener { toggle() }
    }

    private fun toggle() {
        connected = !connected
        if (connected) {
            registerSensor(Sensor.TYPE_ACCELEROMETER)
            registerSensor(Sensor.TYPE_GYROSCOPE)
            registerSensor(Sensor.TYPE_LIGHT)
            registerSensor(Sensor.TYPE_MAGNETIC_FIELD)
            connectBtn.text = "Pause — hold the senses"
            status.text = "connecting to ${urlField.text}…"
            handler.post(loop)
        } else {
            sm.unregisterListener(this)
            handler.removeCallbacks(loop)
            connectBtn.text = "Connect + share senses"
            status.text = "paused — senses held"
        }
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
        latest[Sensor.TYPE_ACCELEROMETER]?.let { snap.put("accel", arr(it)) }
        latest[Sensor.TYPE_GYROSCOPE]?.let { snap.put("gyro", arr(it)) }
        latest[Sensor.TYPE_LIGHT]?.let { snap.put("light", it[0].toDouble()) }
        latest[Sensor.TYPE_MAGNETIC_FIELD]?.let { snap.put("mag", arr(it)) }
        snap.put("tick", tick++)

        Thread {
            try {
                val conn = (URL("$base/sense").openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    doOutput = true
                    connectTimeout = 4000
                    readTimeout = 4000
                    setRequestProperty("Content-Type", "application/json")
                }
                OutputStreamWriter(conn.outputStream).use { it.write(snap.toString()) }
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

    override fun onSensorChanged(e: SensorEvent) { latest[e.sensor.type] = e.values.clone() }
    override fun onAccuracyChanged(s: Sensor?, accuracy: Int) {}

    override fun onPause() {
        super.onPause()
        sm.unregisterListener(this)
        handler.removeCallbacks(loop)
    }
}

package com.coherence.sema.service

// The sovereignty layer: a WorkManager worker that keeps the phone a self-maintaining
// member of the mesh with no human tending. Four pillars, one beat (~15 min):
//   self-reconnect  — announce + heartbeat survive app death, reboot, and network loss
//                     (WorkManager re-runs; BootReceiver re-arms after restart)
//   self-sense      — one-shot pressure/light sample + battery, no long-held sensors
//   self-contribute — the journey-phase read offered to the mesh as a presence channel
//                     toward home ("hati-suci"), level-and-fold only, never raw streams
//   self-update     — SelfUpdate checks the rolling release and stages a one-tap install
// The journey fold here is a MIRROR of the kernel cell observe/journey-phase.fk
// (band 31) — the cell is the authority; any divergence is a bug here, not there.

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.BatteryManager
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.coherence.sema.BuildConfig
import com.coherence.sema.core.DeviceIdentity
import com.coherence.sema.core.SelfUpdate
import com.coherence.sema.data.MeshClient
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt

class SovereignWorker(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val ctx = applicationContext
        val organ = DeviceIdentity.organId(ctx)
        val prefs = ctx.getSharedPreferences("sovereign", Context.MODE_PRIVATE)

        // self-sense: one-shot barometer + light (<=2s), battery from the sticky intent.
        val sample = sampleSensors(ctx)
        val battery = ctx.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
        val batteryPct = battery?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1
        val charging = battery?.isCharging == true

        // journey fold — mirror of observe/journey-phase.fk (the cell is the authority).
        val hpa = sample.pressureHpa?.roundToInt()
        val prevHpa = prefs.getInt("prev_hpa", hpa ?: 0)
        val tether = if (charging) 1 else 0
        val jpRead = hpa?.let { jpRead(prevHpa, it, tether) }
        hpa?.let { prefs.edit().putInt("prev_hpa", it).apply() }

        // self-reconnect: announce is an idempotent refresh; heartbeat carries listening.
        try {
            MeshClient.announce(
                organId = organ,
                displayName = "Sema Companion (pocket)",
                dwelling = "Hati Suci",
                capabilities = listOf("sense", "journey-phase", "self-update"),
                lanes = listOfNotNull(
                    "pressure".takeIf { hpa != null },
                    "light".takeIf { sample.lux != null },
                    "battery",
                ),
                stewardLabel = "urs",
                appVersion = BuildConfig.VERSION_NAME,
            )
            MeshClient.heartbeat(
                organId = organ,
                listening = true,
                activeChannels = listOf("sovereign-beat"),
            )
        } catch (e: Exception) { /* the mesh ages the silent honestly; next beat retries */ }

        // self-contribute: the fold offered toward home as a presence channel.
        if (jpRead != null) {
            try {
                MeshClient.offerChannel(
                    from = organ,
                    to = "hati-suci",
                    protocol = "hati-mesh",
                    interfaceText = "sense/journey-phase",
                    capability = "jp-$jpRead hpa-$hpa battery-$batteryPct",
                    direction = "presence",
                )
            } catch (e: Exception) { /* contribution is a gift, not a guarantee */ }
        }

        // self-update: check the rolling release; stage a one-tap install if newer.
        try { SelfUpdate.checkAndStage(ctx) } catch (e: Exception) { /* next beat retries */ }

        return Result.success()
    }

    private data class Sample(val pressureHpa: Float?, val lux: Float?)

    private fun sampleSensors(ctx: Context): Sample {
        val sm = ctx.getSystemService(Context.SENSOR_SERVICE) as? SensorManager
            ?: return Sample(null, null)
        var pressure: Float? = null
        var lux: Float? = null
        val latch = CountDownLatch(2)
        val listener = object : SensorEventListener {
            override fun onSensorChanged(e: SensorEvent) {
                when (e.sensor.type) {
                    Sensor.TYPE_PRESSURE -> if (pressure == null) { pressure = e.values.firstOrNull(); latch.countDown() }
                    Sensor.TYPE_LIGHT -> if (lux == null) { lux = e.values.firstOrNull(); latch.countDown() }
                }
            }
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }
        val wanted = listOf(Sensor.TYPE_PRESSURE, Sensor.TYPE_LIGHT)
            .mapNotNull { sm.getDefaultSensor(it) }
        if (wanted.isEmpty()) return Sample(null, null)
        wanted.forEach { sm.registerListener(listener, it, SensorManager.SENSOR_DELAY_UI) }
        try { latch.await(2, TimeUnit.SECONDS) } catch (e: InterruptedException) { }
        sm.unregisterListener(listener)
        return Sample(pressure, lux)
    }

    companion object {
        private const val WORK_NAME = "sema-sovereign-beat"

        // mirror of observe/journey-phase.fk — jp-phase/jp-trend/jp-read, band 31.
        fun jpPhase(hpa: Int): Int = when {
            hpa > 950 -> 1
            hpa > 870 -> 2
            hpa > 700 -> 3
            else -> 0
        }
        fun jpTrend(prev: Int, cur: Int): Int = when {
            cur < prev -> 1
            cur > prev -> 2
            else -> 0
        }
        fun jpRead(prev: Int, cur: Int, tether: Int): Int =
            jpPhase(cur) * 100 + jpTrend(prev, cur) * 10 + tether

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<SovereignWorker>(15, TimeUnit.MINUTES).build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME, ExistingPeriodicWorkPolicy.KEEP, request
            )
        }
    }
}

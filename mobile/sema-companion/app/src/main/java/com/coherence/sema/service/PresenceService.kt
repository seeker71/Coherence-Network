package com.coherence.sema.service

// The standing presence: an always-on foreground service so the phone is NEVER off the mesh
// while it has ANY network (wifi or cellular). Foreground = exempt from Doze's background-
// network restriction, which is what silenced the WorkManager beat overnight. Three ways it
// stays present:
//   1. a heartbeat+announce loop every ~5 min (keeps the organ listed, with its name);
//   2. a default-network callback that re-announces the INSTANT a network becomes available
//      (wifi joins, cellular takes over, a hotspot appears) — the "reconnect when networks
//      come available" Urs asked for;
//   3. START_STICKY + start-on-boot, so it revives after kills and restarts.
// Level-and-presence only ever travels — never words, never raw audio.

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import com.coherence.sema.BuildConfig
import com.coherence.sema.core.DeviceIdentity
import com.coherence.sema.data.MeshClient

class PresenceService : Service() {

    private var worker: HandlerThread? = null
    private var handler: Handler? = null
    private var cm: ConnectivityManager? = null
    private var netCb: ConnectivityManager.NetworkCallback? = null
    private val intervalMs = 5 * 60_000L
    @Volatile private var lastBeatAt = 0L

    // Announce (name + presence) then heartbeat. Announce every beat is cheap and keeps the
    // organ named and un-aged; if the network is down it fails quietly and the next network
    // callback re-fires it the moment connectivity returns.
    private fun present(reason: String) {
        val ctx = this
        val organ = DeviceIdentity.organId(ctx)
        try {
            MeshClient.announce(
                organId = organ,
                displayName = DeviceIdentity.displayName(ctx),
                dwelling = "Hati Suci",
                capabilities = listOf("presence", "sense", "self-update"),
                lanes = listOf("wifi", "cellular"),
                stewardLabel = "urs",
                appVersion = BuildConfig.VERSION_NAME,
            )
            MeshClient.heartbeat(organ, listening = true, activeChannels = listOf("presence"))
            lastBeatAt = System.currentTimeMillis()
            android.util.Log.i("sema-presence", "present ($reason) organ=$organ")
        } catch (e: Exception) {
            android.util.Log.i("sema-presence", "present ($reason) FAILED — will retry on next network/beat")
        }
    }

    private val beat = object : Runnable {
        override fun run() {
            present("beat")
            handler?.postDelayed(this, intervalMs)
        }
    }

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIF_ID, notification())
        worker = HandlerThread("sema-presence").also { it.start() }
        handler = Handler(worker!!.looper)

        // Re-announce the instant a network becomes available or changes.
        cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        netCb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                // debounce: skip if we just presented in the last few seconds
                if (System.currentTimeMillis() - lastBeatAt > 4_000L) handler?.post { present("network-available") }
            }
        }
        try { cm?.registerDefaultNetworkCallback(netCb!!) } catch (e: Exception) {}
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        handler?.removeCallbacks(beat)
        handler?.post(beat)
        return START_STICKY
    }

    override fun onDestroy() {
        try { netCb?.let { cm?.unregisterNetworkCallback(it) } } catch (e: Exception) {}
        handler?.removeCallbacks(beat)
        worker?.quitSafely()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun notification(): Notification {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Sema presence", NotificationManager.IMPORTANCE_MIN)
                .apply { description = "Keeps the phone present on the coherence mesh (level and presence only)." }
        )
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Sema is present")
            .setContentText("On the mesh whenever there's a network — level and presence only, never words.")
            .setSmallIcon(android.R.drawable.presence_online)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "sema-presence"
        private const val NOTIF_ID = 71

        fun start(context: Context) {
            context.startForegroundService(Intent(context, PresenceService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, PresenceService::class.java))
        }
    }
}

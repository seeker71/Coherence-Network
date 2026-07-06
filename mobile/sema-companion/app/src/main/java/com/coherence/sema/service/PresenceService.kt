package com.coherence.sema.service

// The standing presence: a small foreground service that keeps the phone's heartbeat on the
// deployed membrane while the app is backgrounded. It sends level-and-presence summaries
// only — never words, never raw sensor streams (the privacy floor is structural).

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import com.coherence.sema.core.DeviceIdentity
import com.coherence.sema.data.MeshClient

class PresenceService : Service() {

    private var worker: HandlerThread? = null
    private var handler: Handler? = null
    private val intervalMs = 5 * 60_000L

    private val beat = object : Runnable {
        override fun run() {
            try {
                MeshClient.heartbeat(
                    DeviceIdentity.organId(this@PresenceService),
                    listening = true,
                    activeChannels = listOf("satsang-session"),
                )
            } catch (e: Exception) { /* the membrane ages the presence honestly if we miss */ }
            handler?.postDelayed(this, intervalMs)
        }
    }

    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIF_ID, notification())
        worker = HandlerThread("sema-presence").also { it.start() }
        handler = Handler(worker!!.looper)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        handler?.removeCallbacks(beat)
        handler?.post(beat)
        return START_STICKY
    }

    override fun onDestroy() {
        handler?.removeCallbacks(beat)
        worker?.quitSafely()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun notification(): Notification {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID, "Sema presence", NotificationManager.IMPORTANCE_MIN
        ).apply { description = "Quiet heartbeat on the coherence mesh" }
        nm.createNotificationChannel(channel)
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Sema is present")
            .setContentText("Heartbeat on the mesh — level and presence only, never words.")
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

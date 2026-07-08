package com.coherence.sema.satsang

// RecordingService — a microphone foreground service so the satsang keeps recording with
// the screen off, the app backgrounded, for the whole session. Android 14+ requires the
// "microphone" foregroundServiceType + FOREGROUND_SERVICE_MICROPHONE permission; started
// from the foreground (the Circle screen) so the OS permits it. Stopping the service
// finalizes the recording and writes a receipt.

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class RecordingService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForegroundMic()
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val file = SatsangRecorder.start(this, stamp)
        if (file == null) {
            // couldn't hold the mic — stop rather than pretend we're recording
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onDestroy() {
        val file = SatsangRecorder.stop()
        if (file != null) writeReceipt(file, SatsangRecorder.startedAt)
        super.onDestroy()
    }

    private fun startForegroundMic() {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Satsang recording", NotificationManager.IMPORTANCE_LOW)
                .apply { description = "Recording the satsang to the phone — audio only, stays on the device." }
        )
        val n: Notification = Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Recording the satsang")
            .setContentText("Audio is being captured on this phone. Tap the app to stop.")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 30) {
            startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIF_ID, n)
        }
    }

    private fun writeReceipt(file: File, startedAt: Long) {
        val ended = System.currentTimeMillis()
        val receipt = JSONObject()
            .put("kind", "satsang-recording")
            .put("file", file.absolutePath)
            .put("bytes", file.length())
            .put("started_at", startedAt)
            .put("ended_at", ended)
            .put("duration_s", ((ended - startedAt) / 1000).coerceAtLeast(0))
            .put("transcribe_hint", "pull to Mac + whisper (ggml-large-v3-turbo)")
        try {
            File(filesDir, "satsang.jsonl").appendText(receipt.toString() + "\n")
        } catch (e: Exception) { /* the recording itself is the receipt of record */ }
    }

    companion object {
        private const val CHANNEL_ID = "sema-satsang-rec"
        private const val NOTIF_ID = 73

        fun start(context: Context) {
            context.startForegroundService(Intent(context, RecordingService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, RecordingService::class.java))
        }
    }
}

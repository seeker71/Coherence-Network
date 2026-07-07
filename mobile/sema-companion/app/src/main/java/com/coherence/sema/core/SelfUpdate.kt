package com.coherence.sema.core

// self-update — the honest floor on stock Android: the app checks the rolling
// release (built by CI on every merge), downloads a newer APK itself, and stages
// a ONE-TAP install notification. Fully-silent installs need device-owner rights;
// pretending otherwise would be theater. One tap per update is the truth here.

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.app.Notification
import androidx.core.content.FileProvider
import com.coherence.sema.BuildConfig
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

object SelfUpdate {
    private const val RELEASE_API =
        "https://api.github.com/repos/seeker71/Coherence-Network/releases/tags/sema-companion-latest"
    private const val CHANNEL_ID = "sema-self-update"
    private const val NOTIF_ID = 72

    fun checkAndStage(context: Context) {
        val release = fetch(RELEASE_API) ?: return
        val json = JSONObject(release)
        val body = json.optString("body", "")
        val remoteCode = Regex("versionCode:\\s*(\\d+)").find(body)
            ?.groupValues?.get(1)?.toIntOrNull() ?: return
        if (remoteCode <= BuildConfig.VERSION_CODE) return

        val assets = json.optJSONArray("assets") ?: return
        var apkUrl: String? = null
        for (i in 0 until assets.length()) {
            val a = assets.getJSONObject(i)
            if (a.optString("name").endsWith(".apk")) {
                apkUrl = a.optString("browser_download_url"); break
            }
        }
        val url = apkUrl ?: return

        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val apk = File(dir, "sema-companion-$remoteCode.apk")
        if (!apk.exists() || apk.length() == 0L) {
            if (!download(url, apk)) return
        }
        notifyReady(context, apk, remoteCode)
    }

    private fun fetch(url: String): String? = try {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 10_000
        conn.readTimeout = 10_000
        conn.setRequestProperty("Accept", "application/vnd.github+json")
        conn.inputStream.bufferedReader().use { it.readText() }
    } catch (e: Exception) { null }

    private fun download(url: String, dest: File): Boolean = try {
        var conn = URL(url).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = 15_000
        conn.readTimeout = 60_000
        // GitHub asset downloads hop hosts; follow one manual redirect if needed.
        if (conn.responseCode in 301..308) {
            val next = conn.getHeaderField("Location")
            conn.disconnect()
            conn = URL(next).openConnection() as HttpURLConnection
            conn.connectTimeout = 15_000
            conn.readTimeout = 60_000
        }
        conn.inputStream.use { input -> dest.outputStream().use { input.copyTo(it) } }
        dest.length() > 0
    } catch (e: Exception) { dest.delete(); false }

    private fun notifyReady(context: Context, apk: File, versionCode: Int) {
        val uri = FileProvider.getUriForFile(
            context, context.packageName + ".fileprovider", apk
        )
        val install = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        val pending = PendingIntent.getActivity(
            context, 0, install,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID, "Sema self-update", NotificationManager.IMPORTANCE_DEFAULT
            ).apply { description = "A newer body is staged; one tap installs it." }
        )
        val n = Notification.Builder(context, CHANNEL_ID)
            .setContentTitle("Sema grew — tap to renew")
            .setContentText("Version $versionCode is downloaded and ready. One tap installs it.")
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        nm.notify(NOTIF_ID, n)
    }
}

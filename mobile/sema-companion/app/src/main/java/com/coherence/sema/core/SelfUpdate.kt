package com.coherence.sema.core

// self-update — the real thing: no tap, no interaction, just update. The app
// checks the rolling release (CI builds on every merge), downloads a newer APK,
// and installs it silently through PackageInstaller with USER_ACTION_NOT_REQUIRED.
//
// The honest floor is named at the mechanism, not hidden behind a dialog:
// Android grants a truly silent commit ONLY when this app holds an install
// privilege — device owner (armed once via adb: `dpm set-device-owner`), or a
// Shizuku/root-backed shell UID. When the privilege is present, commit() returns
// STATUS_SUCCESS with no UI ever. When it is absent, Android ITSELF raises the
// confirm intent (STATUS_PENDING_USER_ACTION) — we surface that as a fallback
// notification rather than fake a silence we didn't earn. Arm the privilege and
// the fallback never fires again. See core/SemaDeviceAdminReceiver.kt.

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import com.coherence.sema.BuildConfig
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

object SelfUpdate {
    private const val RELEASE_API =
        "https://api.github.com/repos/seeker71/Coherence-Network/releases/tags/sema-companion-latest"
    const val ACTION_INSTALL_STATUS = "com.coherence.sema.INSTALL_STATUS"
    private const val CHANNEL_ID = "sema-self-update"
    private const val NOTIF_ID = 72

    fun checkAndStage(context: Context) {
        val release = fetch(RELEASE_API) ?: return
        val json = JSONObject(release)
        val remoteCode = Regex("versionCode:\\s*(\\d+)").find(json.optString("body", ""))
            ?.groupValues?.get(1)?.toIntOrNull() ?: return
        if (remoteCode <= BuildConfig.VERSION_CODE) return

        val assets = json.optJSONArray("assets") ?: return
        var apkUrl: String? = null
        for (i in 0 until assets.length()) {
            val a = assets.getJSONObject(i)
            if (a.optString("name").endsWith(".apk")) { apkUrl = a.optString("browser_download_url"); break }
        }
        val url = apkUrl ?: return

        val dir = File(context.cacheDir, "updates").apply { mkdirs() }
        val apk = File(dir, "sema-companion-$remoteCode.apk")
        if (!apk.exists() || apk.length() == 0L) {
            if (!download(url, apk)) return
        }
        installSilently(context, apk, remoteCode)
    }

    // The silent commit. No dialog, no tap — Android decides on privilege alone.
    private fun installSilently(context: Context, apk: File, versionCode: Int) {
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(
            PackageInstaller.SessionParams.MODE_FULL_INSTALL
        ).apply {
            setAppPackageName(context.packageName)
            if (Build.VERSION.SDK_INT >= 31) {
                setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
            }
        }
        val sessionId = installer.createSession(params)
        installer.openSession(sessionId).use { session ->
            session.openWrite("sema", 0, apk.length()).use { out ->
                apk.inputStream().use { it.copyTo(out) }
                session.fsync(out)
            }
            val statusIntent = Intent(ACTION_INSTALL_STATUS)
                .setPackage(context.packageName)
                .putExtra("versionCode", versionCode)
            val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
            val pending = PendingIntent.getBroadcast(context, sessionId, statusIntent, flags)
            session.commit(pending.intentSender)
        }
    }

    private fun fetch(url: String): String? = try {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 10_000; conn.readTimeout = 10_000
        conn.setRequestProperty("Accept", "application/vnd.github+json")
        conn.inputStream.bufferedReader().use { it.readText() }
    } catch (e: Exception) { null }

    private fun download(url: String, dest: File): Boolean = try {
        var conn = URL(url).openConnection() as HttpURLConnection
        conn.instanceFollowRedirects = true
        conn.connectTimeout = 15_000; conn.readTimeout = 60_000
        if (conn.responseCode in 301..308) {
            val next = conn.getHeaderField("Location"); conn.disconnect()
            conn = URL(next).openConnection() as HttpURLConnection
            conn.connectTimeout = 15_000; conn.readTimeout = 60_000
        }
        conn.inputStream.use { input -> dest.outputStream().use { input.copyTo(it) } }
        dest.length() > 0
    } catch (e: Exception) { dest.delete(); false }

    // Only reached when the install privilege is NOT armed — Android asked for a
    // confirmation we couldn't skip. We surface it honestly; arming device-owner
    // (or Shizuku/root) removes this path entirely.
    class InstallReceiver : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, -1)
            if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                val confirm = if (Build.VERSION.SDK_INT >= 33) {
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                } else {
                    @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_INTENT)
                } ?: return
                confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                nm.createNotificationChannel(
                    NotificationChannel(CHANNEL_ID, "Sema self-update", NotificationManager.IMPORTANCE_DEFAULT)
                        .apply { description = "A newer body is downloaded; the install privilege is not yet armed." }
                )
                val pending = PendingIntent.getActivity(
                    context, 0, confirm,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
                nm.notify(
                    NOTIF_ID,
                    Notification.Builder(context, CHANNEL_ID)
                        .setContentTitle("Sema grew — arm silent update to skip this")
                        .setContentText("Newer body downloaded. Confirm once, or arm device-owner for no-touch updates.")
                        .setSmallIcon(android.R.drawable.stat_sys_download_done)
                        .setContentIntent(pending)
                        .setAutoCancel(true)
                        .build()
                )
            }
            // STATUS_SUCCESS: silent install completed — nothing to say, the body renewed itself.
        }
    }
}

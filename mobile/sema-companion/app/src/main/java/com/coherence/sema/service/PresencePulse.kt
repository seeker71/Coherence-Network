package com.coherence.sema.service

// The Doze-proof layer under the always-on presence. PresenceService (network-reactive, 5-min
// announce+heartbeat loop, foreground) keeps the phone present whenever the device is awake,
// charging, or changing networks. But DEEP Doze — the phone stationary and unplugged overnight —
// is a different regime: a foreground service is NOT exempt from it (that exemption is App
// Standby, not Doze), the CPU is suspended so the Handler loop never ticks, and background
// network is cut device-wide until a maintenance window. That is what aged "Urs's S23 Ultra"
// off the mesh overnight even after the always-on service landed.
//
// Two mechanisms actually pierce deep Doze, and this file owns both:
//   (1) an allow-while-idle alarm — fires even in Doze and briefly allowlists the app for
//       network when it does, waking the CPU the Handler loop cannot;
//   (2) the battery-optimization whitelist — a standing network + wakelock exemption in Doze,
//       asked for once when the steward turns presence on.
// The pulse is ANNOUNCE + heartbeat (never heartbeat alone): a bare heartbeat carries no name,
// so a resurrected mesh entry would read blank. Its identity mirrors PresenceService.present()
// exactly — one organ, one shape, no flapping.

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import com.coherence.sema.BuildConfig
import com.coherence.sema.core.DeviceIdentity
import com.coherence.sema.data.MeshClient

object PresencePulse {
    private const val ALARM_REQUEST = 7101
    const val BEAT_INTERVAL_MS = 15L * 60_000L      // ~15 min: well inside Doze's ~9-min floor
                                                    // for allow-while-idle alarms.

    // announce (name-bearing) + heartbeat (listening). Mirrors PresenceService.present() so the
    // Doze alarm refreshes the SAME organ identity the foreground loop does. MeshClient swallows
    // its own network errors and returns a receipt, so this never throws; we log both legs
    // honestly so the overnight witness line reads true — `adb logcat -s sema-presence`.
    fun beat(ctx: Context): Boolean {
        val organ = DeviceIdentity.organId(ctx)
        val announced = MeshClient.announce(
            organId = organ,
            displayName = DeviceIdentity.displayName(ctx),
            dwelling = "Hati Suci",
            capabilities = listOf("presence", "sense", "self-update"),
            lanes = listOf("wifi", "cellular"),
            stewardLabel = "urs",
            appVersion = BuildConfig.VERSION_NAME,
        )
        val heard = MeshClient.heartbeat(organ, listening = true, activeChannels = listOf("presence"))
        Log.i("sema-presence", "pulse (doze-alarm) announce=${announced.ok} heartbeat=${heard.ok} organ=$organ")
        return announced.ok && heard.ok
    }

    // The Doze-surviving wake. setAndAllowWhileIdle fires even in deep Doze and briefly
    // allowlists the app for network when it does. INEXACT-but-allow-while-idle needs NO
    // exact-alarm permission (setExactAndAllowWhileIdle would, on Android 12+) — a presence
    // beat needs only to arrive, not to land to the second. One-shot, so we re-arm each fire.
    fun scheduleNextBeat(ctx: Context) {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
        val at = System.currentTimeMillis() + BEAT_INTERVAL_MS
        try {
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, alarmIntent(ctx))
        } catch (e: Exception) {
            // Some OEM ROMs cap allow-while-idle alarms; fall back to a plain wake so the beat
            // still fires in maintenance windows rather than going silent.
            am.set(AlarmManager.RTC_WAKEUP, at, alarmIntent(ctx))
        }
    }

    fun cancelBeat(ctx: Context) {
        val am = ctx.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
        am.cancel(alarmIntent(ctx))
    }

    private fun alarmIntent(ctx: Context): PendingIntent {
        val intent = Intent(ctx, PresenceAlarmReceiver::class.java)
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        return PendingIntent.getBroadcast(ctx, ALARM_REQUEST, intent, flags)
    }

    // On this dedicated sovereign phone, the battery-optimization whitelist is what actually
    // lets a backgrounded app hold the network through Doze. We ask ONCE, honestly, when the
    // steward turns presence on. If he declines, the allow-while-idle beat still fires in Doze
    // maintenance windows — just less promptly. Launchable from app context (NEW_TASK).
    fun ensureExemptFromDoze(ctx: Context) {
        val pm = ctx.getSystemService(Context.POWER_SERVICE) as? PowerManager ?: return
        if (pm.isIgnoringBatteryOptimizations(ctx.packageName)) return
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            .setData(Uri.parse("package:${ctx.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try { ctx.startActivity(intent) } catch (e: Exception) { /* the settings screen is absent on some ROMs */ }
    }
}

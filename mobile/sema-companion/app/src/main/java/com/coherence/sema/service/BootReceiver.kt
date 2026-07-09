package com.coherence.sema.service

// The phone re-arms its own sovereignty with no human touch, on the two events
// that could otherwise silence the beat:
//   BOOT_COMPLETED      — after a restart
//   MY_PACKAGE_REPLACED — after the app self-updates (belt-and-suspenders: WorkManager
//                         persists across updates, but this guarantees the beat re-arms
//                         even if that state were ever cleared)
// On both, it re-arms the periodic beat AND restarts the always-on PresenceService, so the
// phone comes back onto the mesh by itself after a reboot or a self-update.

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED -> {
                SovereignWorker.schedule(context)
                PresenceService.start(context)
            }
        }
    }
}

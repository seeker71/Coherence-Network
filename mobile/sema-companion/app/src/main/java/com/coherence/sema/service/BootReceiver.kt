package com.coherence.sema.service

// After a reboot the phone re-arms its own sovereignty: the periodic beat is
// rescheduled with no human touch. The foreground presence service stays a
// foreground-time choice (started from the app); the beat needs no one.

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            SovereignWorker.schedule(context)
        }
    }
}

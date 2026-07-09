package com.coherence.sema.service

// Where the Doze alarm lands. It fires even in deep Doze; we pulse in the brief network window
// the fire grants, then re-arm the next one. This receiver does NOT depend on the foreground
// service being alive — on aggressive OEMs the service can be trimmed overnight, but the alarm
// chain carries presence on its own. PresenceService owns whether the chain runs (it schedules
// the first beat and cancels on stop); once armed, each fire re-arms the next.

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class PresenceAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val app = context.applicationContext
        val pending = goAsync()   // buys a short window to finish the network beat off the main thread
        Thread {
            try {
                PresencePulse.beat(app)
            } finally {
                PresencePulse.scheduleNextBeat(app)   // the chain re-arms itself, beat by beat
                pending.finish()
            }
        }.start()
    }
}

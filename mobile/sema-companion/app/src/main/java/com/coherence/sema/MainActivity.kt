package com.coherence.sema

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import com.coherence.sema.ui.SemaApp
import com.coherence.sema.ui.theme.SemaTheme

class MainActivity : ComponentActivity() {

    private val state: AppState by viewModels()

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
            // Whatever was granted, sense with it; whatever wasn't stays an honest "unread".
            state.startSensing()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SemaTheme { SemaApp(state) }
        }
        state.heartbeatLoop()
        // Arm the sovereignty beat: from this install on, the phone reconnects,
        // senses, contributes, and checks for its own updates with no tending.
        com.coherence.sema.service.SovereignWorker.schedule(this)
        // Always-on presence: never off the mesh while there's any network — re-announces the
        // instant wifi/cellular/hotspot becomes available, and (via PresencePulse) an allow-
        // while-idle alarm carries the beat through the deep, stationary night a foreground
        // service alone cannot. Ask once for the battery-optimization whitelist — the standing
        // Doze network exemption that keeps "Urs's S23 Ultra" listed while it sleeps.
        com.coherence.sema.service.PresenceService.start(this)
        com.coherence.sema.service.PresencePulse.ensureExemptFromDoze(this)
        // Wire the local transport stacks up (LAN/mDNS live; more adapters plug in there).
        com.coherence.sema.mesh.MeshTransports.startAll(this, com.coherence.sema.BuildConfig.VERSION_CODE)
        requestSenses()
    }

    private fun requestSenses() {
        val wanted = mutableListOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.ACCESS_FINE_LOCATION,
        )
        if (Build.VERSION.SDK_INT >= 33) {
            wanted += Manifest.permission.POST_NOTIFICATIONS
        }
        permissionLauncher.launch(wanted.toTypedArray())
    }

    override fun onDestroy() {
        state.stopSensing()
        super.onDestroy()
    }
}

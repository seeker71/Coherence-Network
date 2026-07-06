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

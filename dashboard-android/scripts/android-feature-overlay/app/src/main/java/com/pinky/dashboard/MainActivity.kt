package com.pinky.dashboard

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.pinky.dashboard.core.notification.PinkyNotificationManager
import com.pinky.dashboard.ui.PinkyApp
import com.pinky.dashboard.ui.PinkyViewModel

class MainActivity : ComponentActivity() {
    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* Notification permission is optional; the dashboard remains usable. */ }

    private var openedOrderId by mutableStateOf<String?>(null)
    private val viewModel: PinkyViewModel by viewModels { PinkyViewModel.provideFactory(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        requestNotificationPermissionIfNeeded()
        openedOrderId = intent?.getStringExtra(PinkyNotificationManager.EXTRA_ORDER_ID) ?: intent?.getStringExtra("order_id")
        setContent {
            PinkyApp(viewModel = viewModel, initialOrderId = openedOrderId)
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        (intent.getStringExtra(PinkyNotificationManager.EXTRA_ORDER_ID) ?: intent.getStringExtra("order_id"))?.let { openedOrderId = it }
    }
}

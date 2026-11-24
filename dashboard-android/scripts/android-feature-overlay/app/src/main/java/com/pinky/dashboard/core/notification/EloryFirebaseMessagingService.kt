package com.pinky.dashboard.core.notification

import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class EloryFirebaseMessagingService : FirebaseMessagingService() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        serviceScope.launch {
            EloryPushTokenRegistrar.registerToken(applicationContext, token)
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        if (message.data["type"] != "new_order") return

        val orderId = message.data["order_id"].orEmpty()
        val orderNumber = message.data["order_number"].orEmpty()
        val title = message.data["title"]?.takeIf { it.isNotBlank() }
            ?: message.notification?.title?.takeIf { it.isNotBlank() }
            ?: "🛍️ طلب جديد - Elory"
        val body = message.data["body"]?.takeIf { it.isNotBlank() }
            ?: message.notification?.body?.takeIf { it.isNotBlank() }
            ?: if (orderNumber.isNotBlank()) "تم استلام طلب جديد رقم #" + orderNumber else "تم استلام طلب جديد من المتجر"

        PinkyNotificationManager(applicationContext).showNewOrderNotification(
            title = title,
            body = body,
            orderId = orderId.ifBlank { orderNumber }
        )
    }

    override fun onDestroy() {
        serviceScope.cancel()
        super.onDestroy()
    }
}

package com.pinky.dashboard.core.notification

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Build
import androidx.core.app.NotificationCompat
import com.pinky.dashboard.MainActivity
import com.pinky.dashboard.R
import com.pinky.dashboard.core.util.Formatters
import com.pinky.dashboard.domain.model.Order

class PinkyNotificationManager(private val context: Context) {
    companion object {
        // Matches the deployed Cloudflare Worker FCM payload.
        const val CHANNEL_ID = "elora_orders"
        const val CHANNEL_NAME = "طلبات متجر Elory"
        const val EXTRA_ORDER_ID = "extra_order_id"
    }

    private val notificationManager =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    init {
        createNotificationChannel()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val defaultSound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
            val audioAttributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "تنبيه فوري عند وصول طلب جديد من متجر Elory"
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 350, 180, 350)
                setSound(defaultSound, audioAttributes)
                lockscreenVisibility = Notification.VISIBILITY_PRIVATE
            }
            notificationManager.createNotificationChannel(channel)
        }
    }

    fun showNewOrderNotification(order: Order) {
        val summary = order.items.joinToString(", ") { item -> item.productName + " (" + item.quantity + ")" }
        val body = "طلب جديد #" + order.orderNumber +
            " من " + order.customerName +
            " - " + Formatters.formatCurrencyEgp(order.totalAmount) +
            "\nالمنتجات: " + summary +
            "\nالمحافظة: " + order.governorate
        showNewOrderNotification("🛍️ طلب جديد في متجر Elory!", body, order.id)
    }

    fun showNewOrderNotification(title: String, body: String, orderId: String) {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(EXTRA_ORDER_ID, orderId)
        }
        val notificationId = orderId.hashCode().takeIf { it != 0 } ?: System.currentTimeMillis().toInt()
        val pendingIntent = PendingIntent.getActivity(
            context,
            notificationId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_elory)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_MESSAGE)
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            builder.setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION))
                .setDefaults(NotificationCompat.DEFAULT_VIBRATE)
        }
        notificationManager.notify(notificationId, builder.build())
    }
}

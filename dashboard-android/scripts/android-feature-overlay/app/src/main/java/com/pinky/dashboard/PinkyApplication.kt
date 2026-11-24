package com.pinky.dashboard

import android.app.Application
import com.pinky.dashboard.core.notification.PinkyNotificationManager
import com.pinky.dashboard.core.sync.OrderSyncManager
import com.pinky.dashboard.data.local.PinkyDatabase
import com.pinky.dashboard.data.repository.*
import com.pinky.dashboard.domain.repository.*

class PinkyApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        com.pinky.dashboard.data.remote.SupabaseClient.initPrefs(this)
        PinkyNotificationManager(this)
    }

    val database: PinkyDatabase by lazy { PinkyDatabase.getInstance(this) }
    val orderRepository: OrderRepository by lazy { OrderRepositoryImpl(database) }
    val productRepository: ProductRepository by lazy { ProductRepositoryImpl(database) }
    val categoryRepository: CategoryRepository by lazy { CategoryRepositoryImpl(database) }
    val offerRepository: OfferRepository by lazy { OfferRepositoryImpl(database) }
    val customerRepository: CustomerRepository by lazy { CustomerRepositoryImpl(database) }
    val shippingRepository: ShippingRepository by lazy { ShippingRepositoryImpl(database) }
    val authRepository: AuthRepository by lazy { AuthRepositoryImpl(this) }
    val analyticsRepository: AnalyticsRepository by lazy {
        AnalyticsRepositoryImpl(orderRepository, productRepository, authRepository)
    }
    val syncManager: OrderSyncManager by lazy { OrderSyncManager(this, orderRepository) }
}

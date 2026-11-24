package com.pinky.dashboard.core.notification

import android.content.Context
import android.util.Log
import com.google.android.gms.tasks.Task
import com.google.firebase.messaging.FirebaseMessaging
import com.pinky.dashboard.data.remote.SupabaseClient
import com.pinky.dashboard.data.remote.SupabasePushDeviceRegistrationRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

enum class PushRegistrationResult {
    REGISTERED, ALREADY_REGISTERED, FIREBASE_NOT_CONFIGURED,
    NO_AUTH_SESSION, AUTH_REFRESH_FAILED, SUPABASE_REJECTED
}

object EloryPushTokenRegistrar {
    private const val TAG = "EloryPush"
    private const val PREFS = "elory_push_registration"
    private const val KEY_TOKEN_HASH = "registered_token_sha256"
    private const val KEY_USER_ID = "registered_user_id"

    suspend fun registerCurrentToken(context: Context): PushRegistrationResult = withContext(Dispatchers.IO) {
        val token = try {
            FirebaseMessaging.getInstance().token.awaitResult()
        } catch (error: Exception) {
            Log.w(TAG, "Firebase Messaging is not initialized/configured: " + error.javaClass.simpleName)
            return@withContext PushRegistrationResult.FIREBASE_NOT_CONFIGURED
        }
        registerToken(context.applicationContext, token)
    }

    suspend fun registerToken(context: Context, token: String): PushRegistrationResult = withContext(Dispatchers.IO) {
        if (token.isBlank() || token.length < 100) return@withContext PushRegistrationResult.FIREBASE_NOT_CONFIGURED
        val userId = SupabaseClient.userId?.takeIf { it.isNotBlank() }
            ?: return@withContext PushRegistrationResult.NO_AUTH_SESSION
        if (!SupabaseClient.isAuthenticated) return@withContext PushRegistrationResult.NO_AUTH_SESSION
        if (SupabaseClient.accessToken.isNullOrBlank() && !SupabaseClient.performTokenRefresh()) {
            return@withContext PushRegistrationResult.AUTH_REFRESH_FAILED
        }

        val digest = runCatching {
            java.security.MessageDigest.getInstance("SHA-256")
                .digest(token.toByteArray(Charsets.UTF_8))
                .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
        }.getOrElse { return@withContext PushRegistrationResult.SUPABASE_REJECTED }

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getString(KEY_TOKEN_HASH, null) == digest && prefs.getString(KEY_USER_ID, null) == userId) {
            return@withContext PushRegistrationResult.ALREADY_REGISTERED
        }

        try {
            val response = SupabaseClient.service.registerDashboardPushDevice(
                SupabasePushDeviceRegistrationRequest(token = token, platform = "android")
            )
            if (!response.isSuccessful || response.body()?.ok != true) {
                Log.w(TAG, "Supabase rejected FCM token registration (HTTP " + response.code() + ").")
                return@withContext PushRegistrationResult.SUPABASE_REJECTED
            }
            prefs.edit().putString(KEY_TOKEN_HASH, digest).putString(KEY_USER_ID, userId).apply()
            Log.i(TAG, "FCM token registered for the authenticated dashboard account.")
            PushRegistrationResult.REGISTERED
        } catch (error: Exception) {
            Log.w(TAG, "FCM token registration failed: " + error.javaClass.simpleName)
            PushRegistrationResult.SUPABASE_REJECTED
        }
    }

    private suspend fun <T> Task<T>.awaitResult(): T = suspendCancellableCoroutine { continuation ->
        addOnSuccessListener { value -> if (continuation.isActive) continuation.resume(value) }
        addOnFailureListener { error -> if (continuation.isActive) continuation.resumeWithException(error) }
        addOnCanceledListener { continuation.cancel() }
    }
}

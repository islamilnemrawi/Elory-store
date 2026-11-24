from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT = Path(os.environ["PROJECT_DIR"]).resolve()
OVERLAY = Path(__file__).resolve().parent / "android-feature-overlay" / "app"


def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path = PROJECT / relative
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count == 0 and new in source:
        print(f"Already applied: {label}")
        return
    if count != 1:
        raise SystemExit(f"Refusing partial/ambiguous feature edit ({label}): expected 1 anchor, found {count}.")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"Applied: {label}")


# Copy complete, reviewed application files and resources into the extracted canonical project.
if not OVERLAY.is_dir():
    raise SystemExit("Android feature overlay directory is missing.")
for source in OVERLAY.rglob("*"):
    if not source.is_file():
        continue
    target = PROJECT / "app" / source.relative_to(OVERLAY)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
required_sources = [
    PROJECT / "app/src/main/java/com/pinky/dashboard/core/notification/EloryPushTokenRegistrar.kt",
    PROJECT / "app/src/main/java/com/pinky/dashboard/core/notification/EloryFirebaseMessagingService.kt",
]
missing_sources = [str(path) for path in required_sources if not path.is_file()]
if missing_sources:
    raise SystemExit("Android feature overlay copy is incomplete: " + ", ".join(missing_sources))
print("Copied and verified FCM, notification, application entry and Elory icon sources.")

replace_once(
    "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt",
    '''@JsonClass(generateAdapter = true)
data class SupabaseDashboardPushDeviceDto(
    @Json(name = "id") val id: String,
    @Json(name = "user_id") val userId: String? = null,
    @Json(name = "token") val pushToken: String,
    @Json(name = "platform") val platform: String = "android",
    @Json(name = "active") val active: Boolean = true,
    @Json(name = "created_at") val createdAt: String? = null,
    @Json(name = "updated_at") val updatedAt: String? = null,
    @Json(name = "last_seen_at") val lastSeenAt: String? = null
)
''',
    '''@JsonClass(generateAdapter = true)
data class SupabasePushDeviceRegistrationRequest(
    @Json(name = "p_token") val token: String,
    @Json(name = "p_platform") val platform: String = "android"
)

@JsonClass(generateAdapter = true)
data class SupabasePushDeviceRegistrationResult(
    @Json(name = "ok") val ok: Boolean,
    @Json(name = "user_id") val userId: String? = null
)
''',
    "replace push DTO"
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt",
    '''    // PUSH DEVICES
    @POST("rest/v1/dashboard_push_devices")
    suspend fun registerPushDevice(
        @Body device: SupabaseDashboardPushDeviceDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates"
    ): Response<Unit>
''',
    '''    // Authenticated and idempotent registration through the existing database RPC.
    @POST("rest/v1/rpc/register_dashboard_push_device")
    suspend fun registerDashboardPushDevice(
        @Body request: SupabasePushDeviceRegistrationRequest
    ): Response<SupabasePushDeviceRegistrationResult>
''',
    "replace direct push-table insert with RPC"
)

replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt",
    "import com.pinky.dashboard.core.sync.OrderSyncManager\n",
    "import com.pinky.dashboard.core.sync.OrderSyncManager\nimport com.pinky.dashboard.core.notification.EloryPushTokenRegistrar\n",
    "add token registrar import"
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt",
    "class PinkyViewModel(\n    private val orderRepository: OrderRepository,",
    "class PinkyViewModel(\n    private val appContext: Context,\n    private val orderRepository: OrderRepository,",
    "add app context to view model"
)
view_model_path = PROJECT / "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
view_model = view_model_path.read_text(encoding="utf-8")
start_marker = "            // Register device\n"
end_marker = "\n\n            // Fetch Coupons"
start = view_model.find(start_marker)
end = view_model.find(end_marker, start + 1) if start >= 0 else -1
registration = '''            // Register the real Firebase token only after the staff session is ready.
            // Placeholder tokens are never written to production.
            try {
                when (EloryPushTokenRegistrar.registerCurrentToken(appContext)) {
                    com.pinky.dashboard.core.notification.PushRegistrationResult.REGISTERED,
                    com.pinky.dashboard.core.notification.PushRegistrationResult.ALREADY_REGISTERED ->
                        android.util.Log.i("EloryPush", "Device push registration is ready.")
                    else -> android.util.Log.w("EloryPush", "Push registration awaits Firebase configuration or a valid session.")
                }
            } catch (e: Exception) {
                android.util.Log.w("EloryPush", "Device push registration skipped: " + e.javaClass.simpleName)
            }'''
if start >= 0 and end > start:
    view_model = view_model[:start] + registration + view_model[end:]
elif registration not in view_model:
    raise SystemExit("The previous placeholder push registration block was not found; refusing a blind edit.")
view_model_path.write_text(view_model, encoding="utf-8")
replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt",
    "                    PinkyViewModel(\n                        orderRepository = app.orderRepository,",
    "                    PinkyViewModel(\n                        appContext = context.applicationContext,\n                        orderRepository = app.orderRepository,",
    "pass app context to primary view model factory"
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt",
    "                    PinkyViewModel(\n                        orderRepository = orderRepo,",
    "                    PinkyViewModel(\n                        appContext = context.applicationContext,\n                        orderRepository = orderRepo,",
    "pass app context to fallback view model factory"
)

# The health screen previously inserted test_token_valid_dto_* rows into production.
health_path = PROJECT / "app/src/main/java/com/pinky/dashboard/ui/screens/health/HealthCheckScreen.kt"
health = health_path.read_text(encoding="utf-8")
if "import com.pinky.dashboard.core.notification.EloryPushTokenRegistrar" not in health:
    health = health.replace(
        "import com.pinky.dashboard.data.remote.*\n",
        "import com.pinky.dashboard.data.remote.*\nimport com.pinky.dashboard.core.notification.EloryPushTokenRegistrar\nimport com.pinky.dashboard.core.notification.PushRegistrationResult\n",
        1
    )
start = health.find("            val pushLogs = mutableListOf<String>()")
end_marker = '            updatedResults["push_device_dto"] = ModuleTestResult('
end = health.find(end_marker, start + 1) if start >= 0 else -1
health_test = '''            val pushLogs = mutableListOf<String>()
            var pushError: DiagnosticError? = null
            var pushStatus = TestStatus.PARTIAL
            try {
                when (EloryPushTokenRegistrar.registerCurrentToken(context)) {
                    PushRegistrationResult.REGISTERED -> {
                        pushLogs.add("تم تسجيل رمز Firebase الحقيقي لهذا الجهاز عبر RPC آمن ✓")
                        pushStatus = TestStatus.WORKING
                    }
                    PushRegistrationResult.ALREADY_REGISTERED -> {
                        pushLogs.add("رمز Firebase الحقيقي مسجل بالفعل لهذا الحساب ✓")
                        pushStatus = TestStatus.WORKING
                    }
                    PushRegistrationResult.FIREBASE_NOT_CONFIGURED -> {
                        pushLogs.add("تعذر الحصول على رمز Firebase. أضف google-services.json المطابق للتطبيق.")
                        pushStatus = TestStatus.PARTIAL
                    }
                    PushRegistrationResult.NO_AUTH_SESSION -> {
                        pushLogs.add("يلزم تسجيل الدخول بحساب موظف نشط قبل تسجيل جهاز الإشعارات.")
                        pushStatus = TestStatus.NOT_TESTABLE
                    }
                    PushRegistrationResult.AUTH_REFRESH_FAILED -> {
                        pushLogs.add("تعذر تجديد جلسة Supabase؛ لم يتم تسجيل الجهاز.")
                        pushStatus = TestStatus.FAILED
                    }
                    PushRegistrationResult.SUPABASE_REJECTED -> {
                        pushLogs.add("رفض Supabase تسجيل رمز Firebase الحقيقي. لم يتم إدخال أي رمز تجريبي.")
                        pushStatus = TestStatus.FAILED
                        pushError = DiagnosticError(
                            operation = "registerDashboardPushDevice",
                            tableOrRpc = "register_dashboard_push_device",
                            httpStatus = 0,
                            postgresCode = "PUSH_REGISTRATION_FAILED",
                            errorMessage = "تعذر تسجيل رمز Firebase الحقيقي عبر RPC.",
                            likelyLayer = "Auth / RLS / Firebase configuration"
                        )
                    }
                }
            } catch (e: Exception) {
                pushLogs.add("تعذر اختبار تسجيل الإشعارات: " + e.javaClass.simpleName)
                pushStatus = TestStatus.PARTIAL
            }

'''
if start >= 0 and end > start:
    health = health[:start] + health_test + health[end:]
elif health_test not in health:
    raise SystemExit("The previous fake-device health test was not found; refusing a blind edit.")
health_path.write_text(health, encoding="utf-8")

manifest_path = PROJECT / "app/src/main/AndroidManifest.xml"
manifest_text = manifest_path.read_text(encoding="utf-8")
if "android.permission.POST_NOTIFICATIONS" not in manifest_text:
    manifest_tag = manifest_text.find("<manifest")
    manifest_tag_end = manifest_text.find(">", manifest_tag)
    if manifest_tag < 0 or manifest_tag_end < 0:
        raise SystemExit("Could not safely locate the Android manifest root.")
    manifest_text = (
        manifest_text[:manifest_tag_end + 1]
        + '\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />'
        + manifest_text[manifest_tag_end + 1:]
    )
    manifest_path.write_text(manifest_text, encoding="utf-8")

manifest_path = PROJECT / "app/src/main/AndroidManifest.xml"
manifest_text = manifest_path.read_text(encoding="utf-8")
if "android.permission.POST_NOTIFICATIONS" not in manifest_text:
    manifest_tag = manifest_text.find("<manifest")
    manifest_tag_end = manifest_text.find(">", manifest_tag)
    if manifest_tag < 0 or manifest_tag_end < 0:
        raise SystemExit("Could not safely locate the Android manifest root.")
    manifest_text = (
        manifest_text[:manifest_tag_end + 1]
        + '\\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />'
        + manifest_text[manifest_tag_end + 1:]
    )
    manifest_path.write_text(manifest_text, encoding="utf-8")

replace_once(
    "app/src/main/AndroidManifest.xml",
    '''        <activity
            android:name=".MainActivity"''',
    '''        <service
            android:name=".core.notification.EloryFirebaseMessagingService"
            android:exported="false">
            <intent-filter>
                <action android:name="com.google.firebase.MESSAGING_EVENT" />
            </intent-filter>
        </service>
        <activity
            android:name=".MainActivity"''',
    "declare Firebase messaging service"
)
replace_once(
    "gradle/libs.versions.toml",
    'firebase-auth = { group = "com.google.firebase", name = "firebase-auth" }\n',
    'firebase-auth = { group = "com.google.firebase", name = "firebase-auth" }\nfirebase-messaging = { group = "com.google.firebase", name = "firebase-messaging" }\n',
    "add Firebase Messaging catalog alias"
)
replace_once(
    "app/build.gradle.kts",
    "  implementation(libs.firebase.ai)\n",
    "  implementation(libs.firebase.ai)\n  implementation(libs.firebase.messaging)\n",
    "add Firebase Messaging SDK"
)

# Fail closed if any fake-token generator or legacy REST insert survives this integration.
for relative in (
    "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt",
    "app/src/main/java/com/pinky/dashboard/ui/screens/health/HealthCheckScreen.kt",
):
    source = (PROJECT / relative).read_text(encoding="utf-8")
    if "dummy_token_android_" in source or "test_token_valid_dto_" in source:
        raise SystemExit("A fake push token generator remains in " + relative)
    if "SupabaseDashboardPushDeviceDto" in source or "registerPushDevice(" in source:
        raise SystemExit("A legacy direct push registration remains in " + relative)

service_source = required_sources[1].read_text(encoding="utf-8")
for marker in ('message.data["title"]', 'message.data["body"]', 'message.data["type"] != "new_order"'):
    if marker not in service_source:
        raise SystemExit("FCM data-only notification handling is missing: " + marker)

print("PASS: real FCM registration/receiver, data-only new-order notification handling, default-sound channel, permission, and branded Elory launcher.")

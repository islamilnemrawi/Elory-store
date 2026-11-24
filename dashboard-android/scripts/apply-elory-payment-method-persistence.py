#!/usr/bin/env python3
"""Make the existing Payments screen persist settings and publish them in the CMS JSON.

This patch is intentionally narrow: it adds one optional JSON key, uses an optimistic
compare-and-swap update of the existing site_customizations row, and does not add
or remove tables, policies, methods, or existing settings.
"""
from pathlib import Path
import os

PROJECT = Path(os.environ.get("PROJECT_DIR", "")).resolve()
if not PROJECT.is_dir():
    raise SystemExit("PROJECT_DIR is missing or invalid")

def patch(path: str, old: str, new: str, label: str) -> None:
    file = PROJECT / path
    if not file.exists():
        raise SystemExit(f"Missing required source file for {label}: {file}")
    source = file.read_text(encoding="utf-8")
    if new in source:
        print(f"Already applied: {label}")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one anchor for {label}; found {count}. No ambiguous edit applied.")
    file.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"Applied: {label}")

model = "app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt"
patch(
    model,
    '    @Json(name = "customSections") val customSections: List<CustomSiteSectionConfig>? = null\n)',
    '    @Json(name = "customSections") val customSections: List<CustomSiteSectionConfig>? = null,\n'
    '    @Json(name = "paymentMethods") val paymentMethods: PaymentMethodsConfig? = null\n)\n\n'
    '@JsonClass(generateAdapter = true)\n'
    'data class PaymentMethodsConfig(\n'
    '    @Json(name = "methods") val methods: List<PaymentMethodSiteConfig> = emptyList()\n'
    ')\n\n'
    '@JsonClass(generateAdapter = true)\n'
    'data class PaymentMethodSiteConfig(\n'
    '    @Json(name = "id") val id: String = "",\n'
    '    @Json(name = "key") val key: String = "",\n'
    '    @Json(name = "name") val name: String = "",\n'
    '    @Json(name = "description") val description: String = "",\n'
    '    @Json(name = "isEnabled") val isEnabled: Boolean = true,\n'
    '    @Json(name = "feeOrDiscountText") val feeOrDiscountText: String = ""\n'
    ')',
    "payment methods JSON model"
)

remote = "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt"
patch(
    remote,
    '    @POST("rest/v1/site_customizations")\n'
    '    suspend fun upsertSiteCustomizations(\n'
    '        @Body customizations: SupabaseSiteCustomizationsDto,\n'
    '        @Header("Prefer") prefer: String = "resolution=merge-duplicates"\n'
    '    ): Response<Unit>\n',
    '    @POST("rest/v1/site_customizations")\n'
    '    suspend fun upsertSiteCustomizations(\n'
    '        @Body customizations: SupabaseSiteCustomizationsDto,\n'
    '        @Header("Prefer") prefer: String = "resolution=merge-duplicates"\n'
    '    ): Response<Unit>\n\n'
    '    // Raw JSON access keeps CMS keys unknown to this app intact during a payment-settings-only save.\n'
    '    @GET("rest/v1/site_customizations?select=id,config,updated_at")\n'
    '    suspend fun getSiteCustomizationsRaw(): Response<List<Map<String, Any?>>>\n\n'
    '    @PATCH("rest/v1/site_customizations")\n'
    '    suspend fun patchSiteCustomizationsRaw(\n'
    '        @Query("id") idFilter: String,\n'
    '        @Query("updated_at") updatedAtFilter: String,\n'
    '        @Body updates: Map<String, Any?>,\n'
    '        @Header("Prefer") prefer: String = "return=representation"\n'
    '    ): Response<List<Map<String, Any?>>>\n',
    "safe raw JSON read and compare-and-swap patch API"
)

vm = "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
patch(
    vm,
    'import kotlinx.coroutines.flow.*\nimport kotlinx.coroutines.launch\n',
    'import kotlinx.coroutines.flow.*\nimport kotlinx.coroutines.launch\nimport kotlinx.coroutines.sync.Mutex\nimport kotlinx.coroutines.sync.withLock\n',
    "payment save synchronization imports"
)
patch(
    vm,
    '    val paymentMethods: StateFlow<List<PaymentMethodConfig>> = _paymentMethods.asStateFlow()\n',
    '    val paymentMethods: StateFlow<List<PaymentMethodConfig>> = _paymentMethods.asStateFlow()\n'
    '    private val _lastPersistedPaymentMethods = MutableStateFlow(_paymentMethods.value)\n'
    '    private val paymentMethodsSaveMutex = Mutex()\n',
    "persisted payment state and save mutex"
)
patch(
    vm,
    '                        customSections = config.customSections.sortedBy { it.sortOrder },\n'
    '                        categories = CategoriesConfig(',
    '                        customSections = config.customSections.sortedBy { it.sortOrder },\n'
    '                        paymentMethods = PaymentMethodsConfig(methods = _paymentMethods.value.map { method ->\n'
    '                            PaymentMethodSiteConfig(\n'
    '                                id = method.id, key = method.key, name = method.name,\n'
    '                                description = method.description, isEnabled = method.isEnabled,\n'
    '                                feeOrDiscountText = method.feeOrDiscountText\n'
    '                            )\n'
    '                        }),\n'
    '                        categories = CategoriesConfig(',
    "include payment controls when saving/publishing website configuration"
)
patch(
    vm,
    '                        val cfgObj = draftConfig ?:  customizations.config\n\n'
    '                        currentConfig = currentConfig.copy(',
    '                        val cfgObj = draftConfig ?:  customizations.config\n'
    '                        cfgObj?.paymentMethods?.methods?.takeIf { it.isNotEmpty() }?.let { storedMethods ->\n'
    '                            val defaults = _paymentMethods.value.associateBy { it.key }\n'
    '                            val loadedMethods = storedMethods.map { saved ->\n'
    '                                val fallback = defaults[saved.key]\n'
    '                                PaymentMethodConfig(\n'
    '                                    id = saved.id.ifBlank { fallback?.id ?: saved.key },\n'
    '                                    key = saved.key,\n'
    '                                    name = saved.name.ifBlank { fallback?.name.orEmpty() },\n'
    '                                    description = saved.description.ifBlank { fallback?.description.orEmpty() },\n'
    '                                    isEnabled = saved.isEnabled,\n'
    '                                    feeOrDiscountText = saved.feeOrDiscountText,\n'
    '                                    statusText = if (saved.isEnabled) "نشط" else "معطل",\n'
    '                                    isSecretConfigured = fallback?.isSecretConfigured ?: true\n'
    '                                )\n'
    '                            }\n'
    '                            _paymentMethods.value = loadedMethods\n'
    '                            _lastPersistedPaymentMethods.value = loadedMethods\n'
    '                        }\n\n'
    '                        currentConfig = currentConfig.copy(',
    "restore saved payment methods from CMS JSON"
)
old_save = '''    // Payment methods management
    fun savePaymentMethod(method: PaymentMethodConfig) {
        val current = _paymentMethods.value.toMutableList()
        val idx = current.indexOfFirst { it.key == method.key }
        if (idx >= 0) current[idx] = method else current.add(method)
        _paymentMethods.value = current
    }
'''
new_save = '''    // Payment methods management. The JSON update is compare-and-swap so this
    // screen cannot overwrite unrelated CMS edits made by another dashboard session.
    private fun persistPaymentMethods() {
        viewModelScope.launch {
            paymentMethodsSaveMutex.withLock {
                val target = _paymentMethods.value
                try {
                    val read = SupabaseClient.service.getSiteCustomizationsRaw()
                    if (!read.isSuccessful) {
                        throw IllegalStateException("تعذر قراءة إعدادات الدفع من Supabase (HTTP ${read.code()})")
                    }
                    val row = read.body()?.firstOrNull { (it["id"] as? Number)?.toInt() == 1 }
                        ?: throw IllegalStateException("إعدادات الموقع الأساسية غير موجودة")
                    val updatedAt = row["updated_at"] as? String
                        ?: throw IllegalStateException("تعذر التحقق من إصدار إعدادات الموقع قبل الحفظ")
                    val existingConfig = row["config"] as? Map<*, *> ?: emptyMap<Any?, Any?>()
                    val mergedConfig = existingConfig.entries.associate { it.key.toString() to it.value }.toMutableMap()
                    mergedConfig["paymentMethods"] = mapOf(
                        "methods" to target.map { method ->
                            mapOf(
                                "id" to method.id,
                                "key" to method.key,
                                "name" to method.name,
                                "description" to method.description,
                                "isEnabled" to method.isEnabled,
                                "feeOrDiscountText" to method.feeOrDiscountText
                            )
                        }
                    )
                    val update = mapOf<String, Any?>(
                        "config" to mergedConfig,
                        "updated_at" to java.time.Instant.now().toString()
                    )
                    val write = SupabaseClient.service.patchSiteCustomizationsRaw(
                        idFilter = "eq.1",
                        updatedAtFilter = "eq.$updatedAt",
                        updates = update
                    )
                    if (!write.isSuccessful) {
                        val detail = runCatching { write.errorBody()?.string().orEmpty() }.getOrDefault("")
                        throw IllegalStateException("فشل حفظ إعدادات الدفع (HTTP ${write.code()}): ${detail.take(180)}")
                    }
                    if (write.body().isNullOrEmpty()) {
                        throw IllegalStateException("تغيرت إعدادات الموقع في جلسة أخرى؛ حدّث البيانات ثم أعد حفظ وسيلة الدفع")
                    }
                    _lastPersistedPaymentMethods.value = target
                    notifyUser("تم حفظ إعدادات وسائل الدفع على المتجر")
                } catch (e: Exception) {
                    android.util.Log.e("EloryPayments", "Payment settings save failed", e)
                    if (_paymentMethods.value == target) {
                        _paymentMethods.value = _lastPersistedPaymentMethods.value
                    }
                    notifyUser(e.message?.take(220) ?: "تعذر حفظ وسائل الدفع؛ لم يتم تغيير إعدادات المتجر")
                }
            }
        }
    }

    fun savePaymentMethod(method: PaymentMethodConfig) {
        val current = _paymentMethods.value.toMutableList()
        val idx = current.indexOfFirst { it.key == method.key }
        if (idx >= 0) current[idx] = method else current.add(method)
        _paymentMethods.value = current
        persistPaymentMethods()
    }
'''
patch(vm, old_save, new_save, "persist payment method edits to existing site_customizations row")
old_toggle = '''    fun togglePaymentMethodActive(key: String, isEnabled: Boolean) {
        _paymentMethods.value = _paymentMethods.value.map {
            if (it.key == key) it.copy(isEnabled = isEnabled) else it
        }
    }
'''
new_toggle = '''    fun togglePaymentMethodActive(key: String, isEnabled: Boolean) {
        val updated = _paymentMethods.value.map {
            if (it.key == key) it.copy(isEnabled = isEnabled) else it
        }
        if (updated == _paymentMethods.value) return
        _paymentMethods.value = updated
        persistPaymentMethods()
    }
'''
patch(vm, old_toggle, new_toggle, "persist payment method enable/disable switches")

test_file = PROJECT / "app/src/test/java/com/pinky/dashboard/PaymentMethodsConfigSerializationTest.kt"
if not test_file.exists():
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("""package com.pinky.dashboard

import com.pinky.dashboard.domain.model.PaymentMethodSiteConfig
import com.pinky.dashboard.domain.model.PaymentMethodsConfig
import com.pinky.dashboard.domain.model.SiteCustomizationConfig
import com.squareup.moshi.Moshi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class PaymentMethodsConfigSerializationTest {
    private val adapter = Moshi.Builder().build().adapter(SiteCustomizationConfig::class.java)

    @Test
    fun paymentMethodsRoundTripPreservesCustomerFacingSettings() {
        val expected = PaymentMethodsConfig(
            methods = listOf(
                PaymentMethodSiteConfig(
                    id = "pm_1",
                    key = "credit_card",
                    name = "بطاقات الدفع",
                    description = "الدفع الآمن عبر Paymob",
                    isEnabled = false,
                    feeOrDiscountText = "بدون رسوم"
                )
            )
        )
        val encoded = adapter.toJson(SiteCustomizationConfig(paymentMethods = expected))
        val decoded = adapter.fromJson(encoded)

        assertNotNull(decoded)
        assertEquals(expected, decoded?.paymentMethods)
    }

    @Test
    fun olderSiteConfigWithoutPaymentMethodsRemainsCompatible() {
        val decoded = adapter.fromJson("{}")
        assertNotNull(decoded)
        assertNull(decoded?.paymentMethods)
    }
}
""", encoding="utf-8")
    print("Added payment-method JSON compatibility unit tests.")
else:
    print("Payment-method JSON unit tests already exist.")

print("Payment-method persistence patch completed with all unique anchors verified.")

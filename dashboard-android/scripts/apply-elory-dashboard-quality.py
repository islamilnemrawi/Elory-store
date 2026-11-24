from pathlib import Path
import os

ROOT = Path(os.environ.get("PROJECT_DIR", Path(__file__).resolve().parents[1])).resolve()

def edit(path, old, new, label):
    f = ROOT / path
    s = f.read_text(encoding="utf-8")
    if new in s:
        return
    if old not in s:
        raise SystemExit(f"Missing expected source for {label}: {path}")
    f.write_text(s.replace(old, new, 1), encoding="utf-8")

# Native Android clipboard helper.
p = ROOT / "app/src/main/java/com/pinky/dashboard/ui/components/CopyTextButton.kt"
if not p.exists():
    p.write_text("""package com.pinky.dashboard.ui.components

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext

@Composable
fun CopyTextButton(value: String, contentDescription: String = "نسخ", modifier: Modifier = Modifier) {
    val context = LocalContext.current
    IconButton(onClick = { copyTextToClipboard(context, contentDescription, value) },
        enabled = value.isNotBlank(), modifier = modifier) {
        Icon(Icons.Outlined.ContentCopy, contentDescription = contentDescription)
    }
}
""", encoding="utf-8")

order = "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"
edit(order, "import com.pinky.dashboard.ui.components.OrderStatusBadge\n",
     "import com.pinky.dashboard.ui.components.OrderStatusBadge\nimport com.pinky.dashboard.ui.components.CopyTextButton\n",
     "order clipboard import")
edit(order, "    var noteText by remember { mutableStateOf(order.notes) }\n",
"""    var noteText by remember { mutableStateOf(order.notes) }
    val orderCopyText = remember(order) {
        buildString {
            appendLine("رقم الطلب: ${order.orderNumber}")
            appendLine("كود العميل: ${order.customerOrderCode}")
            appendLine("العميل: ${order.customerName}")
            appendLine("الهاتف: ${order.customerPhone}")
            appendLine("المحافظة: ${order.governorate}")
            appendLine("المركز: ${order.shippingCenter}")
            appendLine("العنوان: ${order.customerAddress}")
            appendLine("الحالة: ${order.status.displayLabel(order.paymentMethod)}")
            appendLine("طريقة الدفع: ${order.paymentMethod.arabicLabel}")
            appendLine("الإجمالي: ${order.totalAmount}")
            appendLine("الشحن: ${order.shippingFee}")
            appendLine("الخصم: ${order.discountAmount}")
            appendLine("المنتجات:")
            order.items.forEachIndexed { i, item ->
                appendLine("${i + 1}. ${item.productName} | الكمية: ${item.quantity} | اللون: ${item.color.orEmpty()} | المقاس: ${item.size.orEmpty()} | السعر: ${item.unitPrice} | الإجمالي: ${item.lineTotal} | كود المنتج: ${item.productCode}")
            }
            if (order.notes.isNotBlank()) appendLine("ملاحظات: ${order.notes}")
        }
    }
""", "order copy summary")
edit(order, 'IconButton(onClick = onDismiss, modifier = Modifier.testTag("close_order_detail_btn")) {',
     'CopyTextButton(value = orderCopyText, contentDescription = "نسخ تفاصيل الطلب", modifier = Modifier.testTag("copy_order_details_btn"))\n                    IconButton(onClick = onDismiss, modifier = Modifier.testTag("close_order_detail_btn")) {',
     "copy order action")
edit(order, 'CopyTextButton(value = orderCopyText, contentDescription = "نسخ تفاصيل الطلب", modifier = Modifier.testTag("copy_order_details_btn"))',
     'CopyTextButton(value = order.customerOrderCode, contentDescription = "نسخ كود العميل")\n                            CopyTextButton(value = orderCopyText, contentDescription = "نسخ تفاصيل الطلب", modifier = Modifier.testTag("copy_order_details_btn"))',
     "copy customer order code separately")


products = "app/src/main/java/com/pinky/dashboard/ui/screens/products/ProductsScreen.kt"
edit(products, "import com.pinky.dashboard.ui.components.OwnerDataResetControls\n",
     "import com.pinky.dashboard.ui.components.OwnerDataResetControls\nimport com.pinky.dashboard.ui.components.CopyTextButton\n",
     "product copy import")
edit(products, "    Card(\n        modifier = Modifier\n            .fillMaxWidth()\n            .testTag(\"product_card_${product.id}\"),",
"""    val productCopyText = buildString {
        appendLine("المنتج: ${product.name}")
        appendLine("كود المنتج: ${product.id}")
        appendLine("القسم: ${product.categoryName}")
        appendLine("السعر: ${product.price}")
        appendLine("السعر السابق: ${product.oldPrice ?: "غير متوفر"}")
        appendLine("المخزون: ${product.stock}")
        appendLine("الألوان: ${product.colors.joinToString()}")
        appendLine("المقاسات: ${product.sizes.joinToString()}")
        appendLine("الحالة: ${if (product.isActive) "نشط" else "غير نشط"}")
        if (currentUser?.canViewWholesale == true) appendLine("سعر الجملة/التكلفة: ${product.wholesalePrice ?: "غير محدد"}")
        if (currentUser?.canViewInternalCode == true) appendLine("كود SKU: ${product.internalCode ?: "—"}")
        if (product.description.isNotBlank()) appendLine("الوصف: ${product.description}")
    }
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("product_card_${product.id}"),""", "product copy summary")
product_file = ROOT / products
product_source = product_file.read_text(encoding="utf-8")
if "copy_product_" not in product_source:
    name_at = product_source.find("text = product.name,")
    if name_at < 0:
        raise SystemExit("Could not find product title for copy action")
    close_at = product_source.find("\n            )", name_at)
    if close_at < 0:
        raise SystemExit("Could not find end of product title")
    close_at += len("\n            )")
    product_source = product_source[:close_at] + '\n            CopyTextButton(value = productCopyText, contentDescription = "نسخ بيانات المنتج", modifier = Modifier.testTag("copy_product_${product.id}"))' + product_source[close_at:]
    product_file.write_text(product_source, encoding="utf-8")


notifications = "app/src/main/java/com/pinky/dashboard/ui/screens/notifications/NotificationsScreen.kt"
# Preserve the already-implemented notification center: it includes read/unread counts,
# filters, empty states, and mark-as-read actions. Avoid layering a duplicate state model.


shipping = "app/src/main/java/com/pinky/dashboard/ui/screens/shipping/ShippingScreen.kt"
shipping_file = ROOT / shipping
shipping_source = shipping_file.read_text(encoding="utf-8")
if "governorates.size" not in shipping_source:
    marker = shipping_source.index("// Search Input")
    insert_at = shipping_source.rfind("\n", 0, marker) + 1
    coverage_block = """                        Spacer(modifier = Modifier.height(8.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                            val activeCount = governorates.count { it.isActive }
                            val centerCount = shippingCenters.count { it.isActive }
                            Surface(modifier = Modifier.weight(1f), shape = RoundedCornerShape(10.dp),
                                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.08f)) {
                                Column(Modifier.padding(10.dp)) {
                                    Text("المحافظات", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text("${governorates.size} إجمالي • $activeCount نشطة", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                }
                            }
                            Surface(modifier = Modifier.weight(1f), shape = RoundedCornerShape(10.dp),
                                color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f)) {
                                Column(Modifier.padding(10.dp)) {
                                    Text("مراكز الشحن", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text("${shippingCenters.size} إجمالي • $centerCount نشط", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(8.dp))

"""
    shipping_source = shipping_source[:insert_at] + coverage_block + shipping_source[insert_at:]
    shipping_file.write_text(shipping_source, encoding="utf-8")


health = "app/src/main/java/com/pinky/dashboard/ui/screens/health/HealthCheckScreen.kt"
health_file = ROOT / health
health_source = health_file.read_text(encoding="utf-8")
if 'updatedResults["section_$tableName"]' not in health_source:
    loop_start = health_source.index("for ((tableName, queryFunc) in tablesToTest) {")
    summary_at = health_source.index('rlsLogs.add("ملخص الفحص:')
    loop_close = health_source.rfind("                }", 0, summary_at)
    if loop_close < loop_start:
        raise SystemExit("Could not locate complete table diagnostic loop")
    loop_end = loop_close + len("                }")
    loop_code = """                for ((tableName, queryFunc) in tablesToTest) {
                    var tableStatus = TestStatus.FAILED
                    var tableError: DiagnosticError? = null
                    val tableLogs = mutableListOf<String>()
                    try {
                        val response = queryFunc()
                        if (response.isSuccessful) {
                            rlsLogs.add("- جدول $tableName: قراءة ناجحة ✓")
                            tableLogs.add("تم تنفيذ استعلام القراءة الفعلي بنجاح.")
                            tableStatus = TestStatus.WORKING
                            succeededTables++
                        } else {
                            val errorStr = response.errorBody()?.string() ?: ""
                            if (response.code() == 403 || errorStr.contains("42501")) {
                                rlsLogs.add("- جدول $tableName: حماية RLS منعت القراءة لهذا الدور")
                                tableLogs.add("قاعدة البيانات رفضت القراءة؛ راجع صلاحيات الدور وسياسة RLS.")
                                tableStatus = TestStatus.PARTIAL
                                tableError = DiagnosticError("select", tableName, response.code(), "42501", errorStr.ifBlank { "RLS restricted this role" }, "RLS / Authorization")
                                restrictedTables++
                            } else {
                                rlsLogs.add("- جدول $tableName: فشل الاستعلام (${response.code()}): $errorStr")
                                tableLogs.add("فشل HTTP ${response.code()}: ${errorStr.take(700)}")
                                tableStatus = TestStatus.FAILED
                                tableError = DiagnosticError("select", tableName, response.code(), "HTTP_${response.code()}", errorStr.take(700), "Database / RLS")
                                failedTables++
                            }
                        }
                    } catch (e: Exception) {
                        rlsLogs.add("- جدول $tableName: فشل الاتصال (${e.message})")
                        tableLogs.add("تعذر تنفيذ طلب الشبكة: ${e.message ?: "Network error"}")
                        tableStatus = TestStatus.FAILED
                        tableError = DiagnosticError("select", tableName, 0, "NET_ERR", e.message ?: "Network error", "Network / Repository")
                        failedTables++
                    }
                    updatedResults["section_$tableName"] = ModuleTestResult(
                        name = tableName,
                        arabicName = when (tableName) {
                            "orders" -> "قسم الطلبات"
                            "products" -> "قسم المنتجات والمخزون"
                            "categories" -> "قسم الأقسام"
                            "offers" -> "قسم العروض"
                            "banners" -> "قسم البنرات"
                            "coupons" -> "قسم الكوبونات"
                            "shipping_governorates" -> "قسم المحافظات والشحن"
                            "shipping_centers" -> "قسم مراكز الشحن"
                            "prime_subscriptions" -> "قسم اشتراكات Prime"
                            "site_customizations" -> "قسم تحرير الموقع"
                            "store_settings" -> "قسم إعدادات المتجر"
                            "staff_profiles" -> "قسم الموظفين والصلاحيات"
                            else -> "قسم $tableName"
                        },
                        dashboardToWebsite = tableStatus,
                        websiteToDashboard = tableStatus,
                        supabaseStatus = tableStatus,
                        logs = tableLogs,
                        error = tableError
                    )
                    testResults = updatedResults.toMap()
                }"""
    health_source = health_source[:loop_start] + loop_code + health_source[loop_end:]
if "items(testResults.values.toList(), key = { it.name })" not in health_source:
    health_source = health_source.replace("items(testResults.values.toList()) { result ->",
        "items(testResults.values.toList(), key = { it.name }) { result ->", 1)
health_file.write_text(health_source, encoding="utf-8")

print("Applied Elory dashboard quality improvements.")

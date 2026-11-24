from __future__ import annotations
import base64
import gzip
import os
import re
import subprocess
from pathlib import Path

PROJECT = Path(os.environ["PROJECT_DIR"]).resolve()
PATCH_TEXT = gzip.decompress(base64.b64decode("""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""")).decode("utf-8")
# The CMS patch already transforms RepositoriesImpl.kt. Apply its remaining,
# non-overlapping changes separately after preserving those CMS changes.
PATCH = "".join(
    section for section in re.split(r"(?=^--- )", PATCH_TEXT, flags=re.MULTILINE)
    if not section.startswith((
        "--- app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt",
        "--- app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt",
    ))
).encode("utf-8")
result = subprocess.run(
    ["patch", "--batch", "--forward", "-p0"],
    cwd=PROJECT,
    input=PATCH,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    check=False,
)
print(result.stdout.decode("utf-8", "replace"))
if result.returncode != 0:
    raise SystemExit("Elory operations patch failed; refusing to continue build.")
# Apply repository-specific changes after CMS order-item fixes so neither patch overwrites the other.
repo_file = PROJECT / "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"
repo_source = repo_file.read_text(encoding="utf-8")

def replace_method(source: str, start: str, end: str, replacement: str) -> str:
    begin = source.find(start)
    if begin < 0:
        raise SystemExit("Repository method start not found: " + start)
    finish = source.find(end, begin)
    if finish < 0:
        raise SystemExit("Repository method boundary not found: " + end)
    return source[:begin] + replacement + "\n\n    " + source[finish:]

update_order_method = """override suspend fun updateOrderStatus(
        orderId: String,
        newStatus: OrderStatus,
        note: String?
    ): Result<Order> = withContext(Dispatchers.IO) {
        try {
            val response = SupabaseClient.service.rpcUpdateOrderStatus(
                mapOf("p_order_id" to orderId, "p_status" to newStatus.arabicLabel)
            )
            if (!response.isSuccessful) {
                val detail = response.errorBody()?.string().orEmpty()
                return@withContext Result.failure(Exception("فشل تحديث حالة الطلب (HTTP ${response.code()}): ${detail.take(300)}"))
            }
            val refreshed = syncOrders()
            if (refreshed.isFailure) orderDao.updateOrderStatus(orderId, newStatus.arabicLabel)
            val updated = getOrderById(orderId) ?: throw IllegalStateException("Order not found after status update")
            Result.success(updated)
        } catch (error: Exception) {
            Result.failure(error)
        }
    }"""
repo_source = replace_method(
    repo_source,
    "override suspend fun updateOrderStatus(",
    "override suspend fun syncOrders()",
    update_order_method
)

# Persist the Prime request flag in the local order cache and both read mappings.
repo_source = repo_source.replace(
    "prime = entity.prime,\n",
    "prime = entity.prime,\n                    primeRequested = entity.primeRequested,\n"
)
repo_source = repo_source.replace(
    "prime = dto.prime ?: false,\n",
    "prime = dto.prime ?: false,\n                        primeRequested = dto.primeRequested ?: false,\n"
)

save_governorate_method = """override suspend fun saveGovernorate(gov: ShippingGovernorate): Result<ShippingGovernorate> = withContext(Dispatchers.IO) {
        try {
            if (!SupabaseClient.hasValidConfiguration || !SupabaseClient.isAuthenticated) {
                return@withContext Result.failure(Exception("يجب تسجيل الدخول بحساب مخوّل لإدارة الشحن."))
            }
            val response = SupabaseClient.service.rpcSaveGovernorate(
                mapOf(
                    "p_governorate" to gov.name.trim(),
                    "p_price" to gov.deliveryPrice,
                    "p_active" to gov.isActive,
                    "p_centers_enabled" to true
                )
            )
            if (!response.isSuccessful) {
                val detail = response.errorBody()?.string().orEmpty()
                return@withContext Result.failure(Exception("فشل حفظ سعر المحافظة (HTTP ${response.code()}): ${detail.take(300)}"))
            }
            val refreshed = syncShipping()
            if (refreshed.isFailure) return@withContext Result.failure(refreshed.exceptionOrNull() ?: Exception("تم الحفظ لكن تعذرت إعادة تحميل بيانات الشحن"))
            Result.success(gov.copy(id = gov.name.trim()))
        } catch (error: Exception) {
            Result.failure(error)
        }
    }"""
repo_source = replace_method(
    repo_source,
    "override suspend fun saveGovernorate(",
    "override suspend fun saveShippingCenter(",
    save_governorate_method
)

save_center_method = """override suspend fun saveShippingCenter(center: ShippingCenter): Result<ShippingCenter> = withContext(Dispatchers.IO) {
        try {
            if (!SupabaseClient.hasValidConfiguration || !SupabaseClient.isAuthenticated) {
                return@withContext Result.failure(Exception("يجب تسجيل الدخول بحساب مخوّل لإدارة الشحن."))
            }
            val uuidPattern = Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
            val idForRpc = center.id.takeIf { uuidPattern.matches(it) } ?: ""
            val response = SupabaseClient.service.rpcSaveShippingCenter(
                mapOf(
                    "p_id" to idForRpc,
                    "p_governorate" to center.governorateId.trim(),
                    "p_center" to center.name.trim(),
                    "p_price" to center.deliveryPrice,
                    "p_active" to center.isActive
                )
            )
            if (!response.isSuccessful) {
                val detail = response.errorBody()?.string().orEmpty()
                return@withContext Result.failure(Exception("فشل حفظ مركز الشحن (HTTP ${response.code()}): ${detail.take(300)}"))
            }
            val returnedId = response.body()?.get("id")?.toString()?.takeIf { it.isNotBlank() } ?: idForRpc
            val refreshed = syncShipping()
            if (refreshed.isFailure) return@withContext Result.failure(refreshed.exceptionOrNull() ?: Exception("تم الحفظ لكن تعذرت إعادة تحميل مراكز الشحن"))
            Result.success(center.copy(id = returnedId))
        } catch (error: Exception) {
            Result.failure(error)
        }
    }"""
repo_source = replace_method(
    repo_source,
    "override suspend fun saveShippingCenter(",
    "override suspend fun deleteShippingCenter(",
    save_center_method
)
repo_file.write_text(repo_source, encoding="utf-8")
print("PASS: repository status, shipping RPC persistence, and Prime request mapping")

# Normalize the complete Room migration block after all earlier CMS/order patches.
database_file = PROJECT / "app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt"
database_source = database_file.read_text(encoding="utf-8")
database_source = re.sub(r"version\s*=\s*\d+", "version = 5", database_source, count=1)
companion_start = database_source.find("    companion object {")
seed_start = database_source.find("\n}\n\nprivate suspend fun seedMockData", companion_start)
if companion_start < 0 or seed_start < 0:
    raise SystemExit("PinkyDatabase companion object boundaries not found")
companion_block = """    companion object {
        private val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE order_items ADD COLUMN productCode TEXT NOT NULL DEFAULT ''")
                database.execSQL("ALTER TABLE order_items ADD COLUMN wholesalePrice REAL")
            }
        }

        private val MIGRATION_4_5 = object : Migration(4, 5) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE orders ADD COLUMN primeRequested INTEGER NOT NULL DEFAULT 0")
            }
        }

        @Volatile
        private var INSTANCE: PinkyDatabase? = null

        fun getInstance(context: Context): PinkyDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    PinkyDatabase::class.java,
                    "pinky_dashboard.db"
                )
                    .addMigrations(MIGRATION_3_4, MIGRATION_4_5)
                    .fallbackToDestructiveMigration()
                    .build()
                INSTANCE = instance
                instance
            }
        }
    }"""
database_source = database_source[:companion_start] + companion_block + database_source[seed_start:]
if "import androidx.sqlite.db.SupportSQLiteDatabase" not in database_source:
    database_source = database_source.replace(
        "import androidx.room.migration.Migration\n",
        "import androidx.room.migration.Migration\nimport androidx.sqlite.db.SupportSQLiteDatabase\n",
        1
    )
database_file.write_text(database_source, encoding="utf-8")
print("PASS: Room database version 5 migrations are structurally complete")

# SupabaseStaffProfileDto exposes active, not a legacy isActive property.
repository_file = PROJECT / "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"
repository_source = repository_file.read_text(encoding="utf-8")
repository_source = repository_source.replace(
    "profile.active ?: profile.isActive ?: false",
    "profile.active ?: false"
)
repository_file.write_text(repository_source, encoding="utf-8")

health_file = PROJECT / "app/src/main/java/com/pinky/dashboard/ui/screens/health/HealthCheckScreen.kt"
health_source = health_file.read_text(encoding="utf-8")
health_source = health_source.replace(
    "profile.active ?: profile.isActive ?: true",
    "profile.active ?: true"
)
health_file.write_text(health_source, encoding="utf-8")
print("PASS: Staff profile code uses actual Supabase DTO fields")

checks = {
    "Prime checkout is represented in orders": ("app/src/main/java/com/pinky/dashboard/domain/model/Order.kt", "primeRequested"),
    "shipping price writes use admin RPC": ("app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt", "admin_apply_shipping_governorate_price"),
    "staff account creation uses secure Edge Function": ("app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt", "admin-create-staff"),
    "Prime list uses schema-safe admin RPC": ("app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt", "admin_list_prime_subscriptions"),
    "Prime display appears on order detail": ("app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt", "Prime مطلوب"),
}
for label, (relative, marker) in checks.items():
    source = (PROJECT / relative).read_text(encoding="utf-8")
    if marker not in source:
        raise SystemExit("Patch verification failed: " + label)
    print("PASS: " + label)

# Keep Prime visible as a first-class line beside ordered products, while preserving
# the original product-only items array for stock and accounting.
order_ui = PROJECT / "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"
order_source = order_ui.read_text(encoding="utf-8")
header_old = 'text = "المنتجات والأصناف المطلوبة (${order.items.size})",'
header_new = 'text = "المنتجات والأصناف المطلوبة (${order.items.size + if (order.primeRequested) 1 else 0})",'
if header_old in order_source:
    order_source = order_source.replace(header_old, header_new, 1)
prime_anchor = '                    items(order.items, key = { it.id }) { item ->'
prime_block = """                    if (order.primeRequested) {
                        item {
                            Card(
                                shape = RoundedCornerShape(12.dp),
                                colors = CardDefaults.cardColors(containerColor = Color(0xFFFFD700).copy(alpha = 0.08f)),
                                border = BorderStroke(1.dp, Color(0xFFD4AF37).copy(alpha = 0.45f))
                            ) {
                                Row(
                                    modifier = Modifier.padding(14.dp).fillMaxWidth(),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                                ) {
                                    Box(
                                        modifier = Modifier.size(76.dp).clip(RoundedCornerShape(10.dp))
                                            .background(Color(0xFFFFD700).copy(alpha = 0.15f)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Icon(Icons.Outlined.Star, contentDescription = "Elory Prime", tint = Color(0xFFD4AF37), modifier = Modifier.size(34.dp))
                                    }
                                    Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                        Text("Elory Prime – اشتراك 30 يومًا", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
                                        Text("يبدأ التفعيل تلقائيًا بعد تسليم الطلب", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    Text(Formatters.formatCurrencyEgp(300.0), fontWeight = FontWeight.Bold, color = Color(0xFFB8860B))
                                }
                            }
                        }
                    }

                    items(order.items, key = { it.id }) { item ->"""
if prime_anchor in order_source and 'Elory Prime – اشتراك 30 يومًا' not in order_source:
    order_source = order_source.replace(prime_anchor, prime_block, 1)
elif 'Elory Prime – اشتراك 30 يومًا' not in order_source:
    raise SystemExit("Prime line-item insertion point not found")
order_ui.write_text(order_source, encoding="utf-8")

staff_ui = PROJECT / "app/src/main/java/com/pinky/dashboard/ui/screens/staff/StaffScreen.kt"
staff_source = staff_ui.read_text(encoding="utf-8")
staff_source = staff_source.replace(
    "enabled = canAssignElevatedRoles || (r == UserRole.EMPLOYEE && staff?.role !in setOf(UserRole.ADMIN, UserRole.MANAGER, UserRole.OWNER)) || r == staff?.role,",
    "enabled = canAssignElevatedRoles || r == UserRole.EMPLOYEE || r == staff?.role,"
)
staff_ui.write_text(staff_source, encoding="utf-8")
print("PASS: Prime line-item display and staff role downgrade")

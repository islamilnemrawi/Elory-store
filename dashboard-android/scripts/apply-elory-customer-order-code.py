from __future__ import annotations

import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path(os.environ["PROJECT_DIR"]).resolve()
SCRIPT_DIR = Path(__file__).resolve().parent
RESOURCE_ROOT = (PROJECT / "app/src/main/res").resolve()


def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path = PROJECT / relative
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count == 0 and new in source:
        print(f"Already applied: {label}")
        return
    if count != 1:
        raise SystemExit(
            f"Refusing partial/ambiguous feature edit ({label}): expected 1 anchor, found {count}."
        )
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"Applied: {label}")


# Install the supplied high-resolution Elory icon and Android adaptive resources.
icon_file = SCRIPT_DIR / "elory-dashboard-icon.webp"
if not icon_file.is_file() or icon_file.stat().st_size < 1000:
    raise SystemExit("The reviewed Elory launcher image is missing or incomplete.")

mipmap_root = RESOURCE_ROOT / "mipmap-nodpi"
drawable_root = RESOURCE_ROOT / "drawable"
drawable_nodpi_root = RESOURCE_ROOT / "drawable-nodpi"
adaptive_root = RESOURCE_ROOT / "mipmap-anydpi-v26"
mipmap_root.mkdir(parents=True, exist_ok=True)
drawable_root.mkdir(parents=True, exist_ok=True)
drawable_nodpi_root.mkdir(parents=True, exist_ok=True)
adaptive_root.mkdir(parents=True, exist_ok=True)
shutil.copy2(icon_file, mipmap_root / "ic_launcher.webp")
shutil.copy2(icon_file, mipmap_root / "ic_launcher_round.webp")
shutil.copy2(icon_file, drawable_nodpi_root / "ic_elory_launcher.webp")

(drawable_root / "ic_launcher_foreground.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<bitmap xmlns:android="http://schemas.android.com/apk/res/android"\n'
    '    android:src="@drawable/ic_elory_launcher"\n'
    '    android:gravity="center" />\n',
    encoding="utf-8",
)
(drawable_root / "ic_launcher_background.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">\n'
    '    <solid android:color="#EB0063" />\n'
    '</shape>\n',
    encoding="utf-8",
)
adaptive_icon = (
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
    '    <background android:drawable="@drawable/ic_launcher_background" />\n'
    '    <foreground android:drawable="@drawable/ic_launcher_foreground" />\n'
    '</adaptive-icon>\n'
)
(adaptive_root / "ic_launcher.xml").write_text(adaptive_icon, encoding="utf-8")
(adaptive_root / "ic_launcher_round.xml").write_text(adaptive_icon, encoding="utf-8")

required_icons = (
    mipmap_root / "ic_launcher.webp",
    mipmap_root / "ic_launcher_round.webp",
    drawable_nodpi_root / "ic_elory_launcher.webp",
    drawable_root / "ic_launcher_foreground.xml",
    drawable_root / "ic_launcher_background.xml",
    adaptive_root / "ic_launcher.xml",
    adaptive_root / "ic_launcher_round.xml",
)
if any(not path.is_file() or path.stat().st_size == 0 for path in required_icons):
    raise SystemExit("Elory launcher resources were not installed completely.")

for xml_resource in (
    drawable_root / "ic_launcher_foreground.xml",
    drawable_root / "ic_launcher_background.xml",
    adaptive_root / "ic_launcher.xml",
    adaptive_root / "ic_launcher_round.xml",
):
    try:
        ET.parse(xml_resource)
    except ET.ParseError as error:
        raise SystemExit(f"Invalid Android launcher XML {xml_resource}: {error}") from error

manifest = PROJECT / "app/src/main/AndroidManifest.xml"
manifest_text = manifest.read_text(encoding="utf-8")
manifest_text, round_icon_count = re.subn(
    r'android:roundIcon="@mipmap/[^"]+"',
    'android:roundIcon="@mipmap/ic_launcher_round"',
    manifest_text,
    count=1,
)
if round_icon_count != 1:
    raise SystemExit("Could not configure the Android round launcher icon.")
manifest.write_text(manifest_text, encoding="utf-8")
print("Installed and verified the new Elory adaptive + round launcher artwork.")

# Customer-facing code is an additional, immutable reference; orderNumber stays internal.
replace_once(
    "app/src/main/java/com/pinky/dashboard/domain/model/Order.kt",
    '    val couponFreeShipping: Boolean = false\n)',
    '    val couponFreeShipping: Boolean = false,\n    val customerOrderCode: String = ""\n)',
    "add customer code to domain model",
)

replace_once(
    "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt",
    '    @Json(name = "coupon_free_shipping") val couponFreeShipping: Boolean? = null\n)',
    '    @Json(name = "coupon_free_shipping") val couponFreeShipping: Boolean? = null,\n'
    '    @Json(name = "customer_order_code") val customerOrderCode: String? = null\n)',
    "read customer order code from Supabase",
)

entities_path = PROJECT / "app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt"
entities_source = entities_path.read_text(encoding="utf-8")
if "import androidx.room.ColumnInfo" not in entities_source.splitlines():
    entity_import = "import androidx.room.Entity" + chr(10)
    if entities_source.count(entity_import) != 1:
        raise SystemExit("Could not find a unique Room Entity import for ColumnInfo.")
    entities_source = entities_source.replace(
        entity_import,
        "import androidx.room.ColumnInfo" + chr(10) + entity_import,
        1,
    )
    entities_path.write_text(entities_source, encoding="utf-8")
    print("Applied: import Room ColumnInfo annotation.")
else:
    print("Already present: Room ColumnInfo annotation import.")

replace_once(
    "app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt",
    '    val couponFreeShipping: Boolean = false\n)',
    '    val couponFreeShipping: Boolean = false,\n'
    '    @ColumnInfo(defaultValue = "\'\'") val customerOrderCode: String = ""\n)',
    "add customer code to cached order entity",
)

# The preceding operations patch installs Room schema 5. Add a dedicated 5 -> 6
# migration so its existing 3 -> 4 -> 5 chain remains intact.
database_path = PROJECT / "app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt"
database_source = database_path.read_text(encoding="utf-8")
database_source, version_count = re.subn(r"(?m)^[ \\t]*version = 5,", "    version = 6,", database_source, count=1)
if version_count != 1:
    raise SystemExit("Expected Room database version 5 before adding customer code.")

for import_line, anchor in (
    ("import androidx.room.migration.Migration\\n", "import androidx.room.RoomDatabase\\n"),
    ("import androidx.sqlite.db.SupportSQLiteDatabase\\n", "import androidx.room.migration.Migration\\n"),
):
    if import_line.rstrip("\\n") not in database_source:
        database_source = database_source.replace(anchor, anchor + import_line, 1)

migration_marker = "        fun getInstance(context: Context): PinkyDatabase {"
migration_block = '''        private val MIGRATION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE orders ADD COLUMN customerOrderCode TEXT NOT NULL DEFAULT ''")
            }
        }

        fun getInstance(context: Context): PinkyDatabase {'''
if "MIGRATION_5_6" not in database_source:
    if database_source.count(migration_marker) != 1:
        raise SystemExit("Room 5-to-6 migration insertion point is not unique.")
    database_source = database_source.replace(migration_marker, migration_block, 1)

builder_migrations = ".addMigrations(MIGRATION_3_4, MIGRATION_4_5)"
if builder_migrations not in database_source:
    raise SystemExit("Existing Room 3-to-4 and 4-to-5 migrations were not found.")
database_source = database_source.replace(
    builder_migrations,
    ".addMigrations(MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6)",
    1,
)
database_path.write_text(database_source, encoding="utf-8")
print("Applied: non-destructive Room 5-to-6 migration for customer order codes.")

# Preserve the code in both local-entity -> domain-model repository paths.
repository_path = PROJECT / "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"
repository_source = repository_path.read_text(encoding="utf-8")
pattern = r'(?m)^(\s*)couponFreeShipping = entity\.couponFreeShipping$'
repository_source, mapping_count = re.subn(
    pattern,
    lambda match: (
        match.group(1) + "couponFreeShipping = entity.couponFreeShipping,\n"
        + match.group(1) + "customerOrderCode = entity.customerOrderCode"
    ),
    repository_source,
)
if mapping_count != 2:
    raise SystemExit(f"Expected exactly two entity-to-domain order mappings, found {mapping_count}.")
repository_path.write_text(repository_source, encoding="utf-8")
print("Applied: preserve customer code in both cached-order read paths.")

replace_once(
    "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt",
    "                        orderNumber = dto.orderNumber,\n",
    "                        orderNumber = dto.orderNumber,\n"
    "                        customerOrderCode = dto.customerOrderCode.orEmpty(),\n",
    "sync Supabase customer code into Room",
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt",
    "            val entity = OrderEntity(\n"
    "                id = order.id,\n"
    "                orderNumber = order.orderNumber,\n",
    "            val entity = OrderEntity(\n"
    "                id = order.id,\n"
    "                orderNumber = order.orderNumber,\n"
    "                customerOrderCode = order.customerOrderCode,\n",
    "preserve customer code in local order cache only",
)

replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrdersScreen.kt",
    "                order.orderNumber.contains(searchQuery, ignoreCase = true) ||\n",
    "                order.orderNumber.contains(searchQuery, ignoreCase = true) ||\n"
    "                order.customerOrderCode.contains(searchQuery, ignoreCase = true) ||\n",
    "search order screen by customer code",
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrdersScreen.kt",
    '                placeholder = { Text("بحث برقم الطلب، اسم العميل، أو رقم الهاتف...") },',
    '                placeholder = { Text("بحث برمز العميل، الرقم التسلسلي، الاسم أو الهاتف...") },',
    "clarify customer code search",
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrdersScreen.kt",
    '                    Text(\n'
    '                        text = "#${order.orderNumber}",\n'
    '                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),\n'
    '                        color = PinkPrimary\n'
    '                    )\n'
    '                    Text(\n'
    '                        text = Formatters.formatOrderDate(order.createdAt),',
    '                    Text(\n'
    '                        text = "#${order.orderNumber}",\n'
    '                        style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),\n'
    '                        color = PinkPrimary\n'
    '                    )\n'
    '                    if (order.customerOrderCode.isNotBlank()) {\n'
    '                        Text(\n'
    '                            text = "رمز العميل: ${order.customerOrderCode}",\n'
    '                            style = MaterialTheme.typography.bodySmall,\n'
    '                            color = MaterialTheme.colorScheme.onSurfaceVariant\n'
    '                        )\n'
    '                    }\n'
    '                    Text(\n'
    '                        text = Formatters.formatOrderDate(order.createdAt),',
    "show customer code beside internal serial",
)

replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt",
    '                        Text(\n'
    '                            text = Formatters.formatOrderDate(order.createdAt),\n'
    '                            style = MaterialTheme.typography.bodySmall,\n'
    '                            color = MaterialTheme.colorScheme.onSurfaceVariant\n'
    '                        )',
    '                        Text(\n'
    '                            text = Formatters.formatOrderDate(order.createdAt),\n'
    '                            style = MaterialTheme.typography.bodySmall,\n'
    '                            color = MaterialTheme.colorScheme.onSurfaceVariant\n'
    '                        )\n'
    '                        if (order.customerOrderCode.isNotBlank()) {\n'
    '                            Text(\n'
    '                                text = "رمز العميل: ${order.customerOrderCode}",\n'
    '                                style = MaterialTheme.typography.bodySmall,\n'
    '                                color = MaterialTheme.colorScheme.onSurfaceVariant\n'
    '                            )\n'
    '                        }',
    "show customer code in order detail",
)

replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/components/GlobalSearchDialog.kt",
    "            it.orderNumber.contains(searchQuery, ignoreCase = true) ||\n",
    "            it.orderNumber.contains(searchQuery, ignoreCase = true) ||\n"
    "            it.customerOrderCode.contains(searchQuery, ignoreCase = true) ||\n",
    "global search by customer order code",
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/components/GlobalSearchDialog.kt",
    '                    placeholder = { Text("ابحث برقم الطلب، اسم العميل، المنتج، الكوبون أو القسم...") },',
    '                    placeholder = { Text("ابحث برمز الطلب، رقمه الداخلي، العميل، المنتج أو الكوبون...") },',
    "clarify global search includes order code",
)
replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/components/GlobalSearchDialog.kt",
    '                                    title = "${order.orderNumber} - ${order.customerName}",',
    '                                    title = "${order.customerOrderCode.ifBlank { "بدون رمز" }} • #${order.orderNumber} - ${order.customerName}",',
    "show customer code and internal serial in global results",
)

required_markers = {
    "app/src/main/java/com/pinky/dashboard/domain/model/Order.kt": "customerOrderCode",
    "app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt": "customerOrderCode",
    "app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt": "MIGRATION_3_4",
    "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt": "customer_order_code",
    "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt": "dto.customerOrderCode.orEmpty()",
    "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrdersScreen.kt": "order.customerOrderCode.contains",
    "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt": "رمز العميل:",
    "app/src/main/java/com/pinky/dashboard/ui/components/GlobalSearchDialog.kt": "it.customerOrderCode.contains",
}
for relative, marker in required_markers.items():
    if marker not in (PROJECT / relative).read_text(encoding="utf-8"):
        raise SystemExit("Customer order code integration check failed in " + relative)

database_source = (PROJECT / "app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt").read_text(encoding="utf-8")
if "version = 6" not in database_source or "MIGRATION_5_6" not in database_source or ".addMigrations(MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6)" not in database_source:
    raise SystemExit("Room 5-to-6 customer-code migration is not registered.")
print("PASS: customer code DTO/cache/search/detail and non-destructive Room migration are installed.")

#!/usr/bin/env python3
"""Persist the existing product-weight input end-to-end without data loss."""
from pathlib import Path
import os

PROJECT = Path(os.environ.get("PROJECT_DIR", "")).resolve()
if not PROJECT.is_dir():
    raise SystemExit("PROJECT_DIR is missing or invalid")

def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path = PROJECT / relative
    if not path.is_file():
        raise SystemExit(f"Missing source file for {label}: {relative}")
    source = path.read_text(encoding="utf-8")
    if new in source:
        print(f"Already applied: {label}")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one source anchor for {label}; found {count}.")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"Applied: {label}")

model = "app/src/main/java/com/pinky/dashboard/domain/model/Product.kt"
replace_once(
    model,
    "    val isFeatured: Boolean = false,\n    val createdAt: Long = System.currentTimeMillis()\n)",
    "    val isFeatured: Boolean = false,\n    val createdAt: Long = System.currentTimeMillis(),\n    val weight: Double? = null // Product weight in grams; nullable for older products\n)",
    "product domain weight field"
)

entity = "app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt"
replace_once(
    entity,
    "    val isFeatured: Boolean,\n    val createdAt: Long,\n    val isSynced: Boolean = true\n)",
    "    val isFeatured: Boolean,\n    val createdAt: Long,\n    val isSynced: Boolean = true,\n    val weight: Double? = null\n)",
    "nullable Room product weight column"
)

database = "app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt"
replace_once(
    database,
    "    version = 8,\n    exportSchema = false",
    "    version = 9,\n    exportSchema = false",
    "Room database version"
)
replace_once(
    database,
    '''        private val MIGRATION_7_8 = object : Migration(7, 8) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE orders ADD COLUMN carrierShippingCost REAL")
            }
        }
''',
    '''        private val MIGRATION_7_8 = object : Migration(7, 8) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE orders ADD COLUMN carrierShippingCost REAL")
            }
        }

        // Adds a nullable column only; existing products and all other cached records remain intact.
        private val MIGRATION_8_9 = object : Migration(8, 9) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE products ADD COLUMN weight REAL")
            }
        }
''',
    "non-destructive Room 8 to 9 migration"
)
replace_once(
    database,
    ".addMigrations(MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6, MIGRATION_6_7, MIGRATION_7_8)",
    ".addMigrations(MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6, MIGRATION_6_7, MIGRATION_7_8, MIGRATION_8_9)",
    "register Room 8 to 9 migration"
)

dialog = "app/src/main/java/com/pinky/dashboard/ui/screens/products/ProductEditDialog.kt"
replace_once(
    dialog,
    '    var weightText by remember { mutableStateOf("") } // Weight field placeholder state for future schema link',
    '    var weightText by remember { mutableStateOf(initialProduct?.weight?.toString() ?: "") }',
    "restore product weight in edit dialog"
)
replace_once(
    dialog,
    '''                                        val stock = stockText.toIntOrNull() ?: 0
                                        val discount = discountText.toIntOrNull()
''',
    '''                                        val stock = stockText.toIntOrNull() ?: 0
                                        val discount = discountText.toIntOrNull()
                                        val normalizedWeight = weightText.trim().replace(',', '.')
                                        val weight = normalizedWeight.takeIf { it.isNotEmpty() }?.toDoubleOrNull()
                                        if (normalizedWeight.isNotEmpty() && (weight == null || weight < 0.0)) {
                                            throw IllegalArgumentException("أدخلي وزنًا صحيحًا بالجرام، أو اتركي الحقل فارغًا")
                                        }
''',
    "validate optional product weight"
)
replace_once(
    dialog,
    '''                                            isActive = isActive,
                                            isFeatured = isFeatured,
                                            createdAt = initialProduct?.createdAt ?: System.currentTimeMillis()
''',
    '''                                            isActive = isActive,
                                            isFeatured = isFeatured,
                                            createdAt = initialProduct?.createdAt ?: System.currentTimeMillis(),
                                            weight = weight
''',
    "pass weight from product editor into saved product"
)

repository = "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"
replace_once(
    repository,
    "                colors = product.colors,\n                sizes = product.sizes,\n                gallery = product.gallery\n",
    "                colors = product.colors,\n                sizes = product.sizes,\n                gallery = product.gallery,\n                weight = product.weight\n",
    "include weight in Supabase product upsert"
)
replace_once(
    repository,
    '''                wholesalePrice = product.wholesalePrice,
                internalCode = product.internalCode,
                stock = product.stock,
                colorsJson = product.colors.joinToString(","),''',
    '''                wholesalePrice = product.wholesalePrice,
                internalCode = product.internalCode,
                stock = product.stock,
                weight = product.weight,
                colorsJson = product.colors.joinToString(","),''',
    "persist product weight in Room cache"
)
replace_once(
    repository,
    "                        wholesalePrice = dto.wholesalePrice,\n                        internalCode = dto.code,\n                        stock = dto.stock ?: 0,",
    "                        wholesalePrice = dto.wholesalePrice,\n                        internalCode = dto.code,\n                        stock = dto.stock ?: 0,\n                        weight = dto.weight,",
    "restore product weight during Supabase synchronization"
)
replace_once(
    repository,
    "            isFeatured = isFeatured,\n            createdAt = createdAt\n        )",
    "            isFeatured = isFeatured,\n            createdAt = createdAt,\n            weight = weight\n        )",
    "restore cached product weight in domain model"
)

test = PROJECT / "app/src/test/java/com/pinky/dashboard/ProductWeightSerializationTest.kt"
if not test.exists():
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text("""package com.pinky.dashboard

import com.pinky.dashboard.data.remote.SupabaseProductAdminDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class ProductWeightSerializationTest {
    private val adapter = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()
        .adapter(SupabaseProductAdminDto::class.java)

    @Test
    fun productWeightIsReadFromSupabaseAdminRows() {
        val dto = adapter.fromJson(
            "{\\\"id\\\":\\\"00000000-0000-0000-0000-000000000001\\\",\\\"name\\\":\\\"Test\\\",\\\"price\\\":100,\\\"weight\\\":350.5}"
        )
        assertNotNull(dto)
        assertEquals(350.5, dto?.weight ?: 0.0, 0.0001)
    }
}
""", encoding="utf-8")
    print("Added Supabase product-weight serialization regression test.")

print("Product weight persistence patch completed.")

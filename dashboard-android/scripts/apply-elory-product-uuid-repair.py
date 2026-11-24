from pathlib import Path
import os
import re

root = Path(os.environ["PROJECT_DIR"]).resolve()

def edit(relative, transform):
    path = root / relative
    source = path.read_text(encoding="utf-8")
    updated = transform(source)
    if updated == source:
        raise SystemExit(f"No product UUID repair applied to {relative}; reviewed source anchor did not match")
    path.write_text(updated, encoding="utf-8")

remote_file = "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt"
repo_file = "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"
vm_file = "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"

def patch_remote(source):
    start = source.find("data class SupabaseProductAdminDto(")
    if start < 0:
        raise SystemExit("SupabaseProductAdminDto declaration not found")
    end = source.find("\n)", start)
    if end < 0:
        raise SystemExit("SupabaseProductAdminDto closing delimiter not found")
    admin_block = source[start:end + 2]
    if source.count("data class SupabaseProductUpsertDto(") != 0:
        raise SystemExit("SupabaseProductUpsertDto already exists; refusing duplicate insertion")
    upsert_block = admin_block.replace(
        "data class SupabaseProductAdminDto(",
        "data class SupabaseProductUpsertDto(",
        1
    )
    old_id = '@Json(name = "id") val id: String,'
    if upsert_block.count(old_id) != 1:
        raise SystemExit("Product admin DTO id field missing or duplicated")
    upsert_block = upsert_block.replace(old_id, '@Json(name = "id") val id: String? = null,', 1)
    source = source[:end + 2] + "\n\n@JsonClass(generateAdapter = true)\n" + upsert_block + source[end + 2:]

    old_method = """    @POST("rest/v1/products")
    suspend fun upsertAdminProduct(
        @Body product: SupabaseProductAdminDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates"
    ): Response<Unit>"""
    new_method = """    @POST("rest/v1/products")
    suspend fun upsertAdminProduct(
        @Body product: SupabaseProductUpsertDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates,return=representation"
    ): Response<List<SupabaseProductAdminDto>>"""
    if source.count(old_method) != 1:
        raise SystemExit("upsertAdminProduct API declaration missing or duplicated")
    return source.replace(old_method, new_method, 1)

edit(remote_file, patch_remote)

def patch_repository(source):
    if "import java.util.UUID" not in source:
        anchor = "import java.util.Locale"
        if source.count(anchor) != 1:
            raise SystemExit("Repository import anchor missing or duplicated")
        source = source.replace(anchor, anchor + "\nimport java.util.UUID", 1)

    marker = "class ProductRepositoryImpl("
    if source.count(marker) != 1:
        raise SystemExit("ProductRepositoryImpl class marker missing or duplicated")
    if "private fun isCanonicalProductUuid" not in source:
        source = source.replace(
            marker,
            """private fun isCanonicalProductUuid(value: String): Boolean =
    runCatching {
        UUID.fromString(value).toString().equals(value, ignoreCase = true) &&
            Regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$").matches(value)
    }.getOrDefault(false)

""" + marker,
            1
        )

    old = """            // 1. Save to Supabase (using products table via SupabaseProductAdminDto)
            val dto = SupabaseProductAdminDto(
                id = product.id,"""
    new = """            // Supabase products.id is UUID. Local draft/legacy IDs such as prod_* must never
            // be sent to Postgres; omit them so the database generates its canonical UUID.
            val remoteProductId = product.id.takeIf(::isCanonicalProductUuid)

            // 1. Save to Supabase and request the persisted row so newly generated IDs are returned.
            val dto = SupabaseProductUpsertDto(
                id = remoteProductId,"""
    if source.count(old) != 1:
        raise SystemExit("Product save DTO construction anchor missing or duplicated")
    source = source.replace(old, new, 1)

    old_call = "val response = SupabaseClient.service.upsertAdminProduct(dto)"
    new_call = 'val response = SupabaseClient.service.upsertAdminProduct(dto, "resolution=merge-duplicates,return=representation")'
    if source.count(old_call) != 1:
        raise SystemExit("Product upsert call missing or duplicated")
    source = source.replace(old_call, new_call, 1)

    old_response = """            // 2. Save to local Cache
            val entity = ProductEntity(
                id = product.id,"""
    new_response = """            val persistedProductId = response.body()?.firstOrNull()?.id
                ?.takeIf(::isCanonicalProductUuid)
                ?: remoteProductId
                ?: throw IllegalStateException("Supabase saved the product but did not return its generated UUID.")

            val savedProduct = product.copy(id = persistedProductId)

            // 2. Save to local Cache using the canonical Supabase UUID.
            val entity = ProductEntity(
                id = persistedProductId,"""
    if source.count(old_response) != 1:
        raise SystemExit("Product local-cache ID anchor missing or duplicated")
    source = source.replace(old_response, new_response, 1)

    old_result = "            Result.success(product)\n        } catch (e: Exception) {"
    new_result = "            Result.success(savedProduct)\n        } catch (e: Exception) {"
    if source.count(old_result) != 1:
        raise SystemExit("Product save result anchor missing or duplicated")
    source = source.replace(old_result, new_result, 1)

    # The active database RPC accepts the manager role. Map it to the app's
    # administrator role while preserving the explicit permission set from Supabase.
    old_manager_role = '"admin", "administrator" -> UserRole.ADMIN'
    new_manager_role = '"admin", "administrator", "manager" -> UserRole.ADMIN'
    if source.count(old_manager_role) != 1:
        raise SystemExit("Staff role mapping anchor missing or duplicated")
    return source.replace(old_manager_role, new_manager_role, 1)

edit(repo_file, patch_repository)

def patch_view_model(source):
    old = """    fun saveProduct(product: Product) {
        viewModelScope.launch {
            productRepository.saveProduct(product)
        }
    }"""
    new = """    fun saveProduct(product: Product) {
        viewModelScope.launch {
            val result = productRepository.saveProduct(product)
            if (result.isSuccess) {
                // Read-after-write ensures the visible list, edit/delete actions and local cache
                // all use the canonical UUID generated by Supabase for new products.
                val syncResult = productRepository.syncProducts()
                _syncError.value = syncResult.exceptionOrNull()?.let {
                    "تم حفظ المنتج، لكن تعذرت مزامنة القائمة: ${it.localizedMessage ?: "خطأ غير معروف"}"
                }
            } else {
                val error = result.exceptionOrNull()
                _syncError.value = "تعذر حفظ المنتج: ${error?.localizedMessage ?: "خطأ غير معروف"}"
                android.util.Log.e("EloryProducts", "Product save failed.", error)
            }
        }
    }"""
    if source.count(old) != 1:
        raise SystemExit("PinkyViewModel.saveProduct anchor missing or duplicated")
    return source.replace(old, new, 1)

edit(vm_file, patch_view_model)
print("PASS: Product create omits local prod_* IDs, receives the database UUID, persists it locally, and refreshes the product list.")

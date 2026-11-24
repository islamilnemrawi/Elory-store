from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()


def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"Missing required source file for {label}: {relative}")
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count == 0 and new in source:
        print(f"Already applied: {label}")
        return
    if count != 1:
        raise SystemExit(f"Expected exactly one anchor for {label}; found {count}")
    updated = source.replace(old, new, 1)
    path.write_text(updated, encoding="utf-8")
    print(f"PASS: {label}")


API = "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt"
REPOSITORY = "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"

replace_once(
    API,
'''    // Admin products table for CRUD and dashboards. Explicit Range headers support catalogs > 1,000 rows.
    @GET("rest/v1/products")
    suspend fun getAdminProducts(
        @Query("select") select: String,
        @Query("order") order: String,
        @Header("Range") range: String,
        @Header("Range-Unit") rangeUnit: String
    ): Response<List<SupabaseProductAdminDto>>
''',
'''    // Staff product reads use a server-side permission-filtered RPC.
    // The public products table is intentionally restricted to catalog-safe columns.
    @POST("rest/v1/rpc/admin_list_products")
    suspend fun getAdminProducts(
        @Body parameters: Map<String, @JvmSuppressWildcards Any>
    ): Response<List<SupabaseProductAdminDto>>
''',
    "Route dashboard product reads through the permission-filtered RPC",
)

replace_once(
    REPOSITORY,
'''                val range = "$offset-${offset + SupabaseConfig.PAGE_SIZE - 1}"
                val response = SupabaseClient.service.getAdminProducts("*", "id.asc", range, "items")
''',
'''                val response = SupabaseClient.service.getAdminProducts(
                    mapOf(
                        "p_limit" to SupabaseConfig.PAGE_SIZE,
                        "p_offset" to offset
                    )
                )
''',
    "Use bounded limit/offset parameters for admin product pagination",
)

replace_once(
    "app/src/main/java/com/pinky/dashboard/ui/screens/health/HealthCheckScreen.kt",
'''                        SupabaseClient.service.getAdminProducts(
                            select = "*",
                            order = "id.asc",
                            range = "0-0",
                            rangeUnit = "items"
                        )
''',
'''                        SupabaseClient.service.getAdminProducts(
                            mapOf("p_limit" to 1, "p_offset" to 0)
                        )
''',
    "Keep the products RLS diagnostic on the secured staff RPC",
)

replace_once(
    API,
'''    @POST("rest/v1/products")
    suspend fun upsertAdminProduct(
        @Body product: SupabaseProductUpsertDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates,return=representation"
    ): Response<List<SupabaseProductAdminDto>>
''',
'''    @POST("rest/v1/products")
    suspend fun upsertAdminProduct(
        @Body product: SupabaseProductUpsertDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates,return=minimal"
    ): Response<Unit>
''',
    "Keep product upserts compatible with protected-column SELECT grants",
)

replace_once(
    REPOSITORY,
'''            val remoteProductId = product.id.takeIf(::isCanonicalProductUuid)
''',
'''            // Generate the UUID client-side so return=minimal can be used safely
            // without asking PostgREST to SELECT protected product columns.
            val remoteProductId = product.id.takeIf(::isCanonicalProductUuid)
                ?: java.util.UUID.randomUUID().toString()
''',
    "Generate canonical product UUIDs before a minimal-response upsert",
)

replace_once(
    REPOSITORY,
'''            val response = SupabaseClient.service.upsertAdminProduct(dto, "resolution=merge-duplicates,return=representation")
''',
'''            val response = SupabaseClient.service.upsertAdminProduct(dto, "resolution=merge-duplicates,return=minimal")
''',
    "Avoid RETURNING protected product columns during save",
)

replace_once(
    REPOSITORY,
'''            val persistedProductId = response.body()?.firstOrNull()?.id
                ?.takeIf(::isCanonicalProductUuid)
                ?: remoteProductId
                ?: throw IllegalStateException("Supabase saved the product but did not return its generated UUID.")
''',
'''            // The same canonical ID was sent in the upsert body; the server
            // intentionally returns no row to preserve column-level privacy.
            val persistedProductId = remoteProductId
''',
    "Retain the product UUID without requiring a privileged row response",
)

api_source = (ROOT / API).read_text(encoding="utf-8")
repository_source = (ROOT / REPOSITORY).read_text(encoding="utf-8")
if '@POST("rest/v1/rpc/admin_list_products")' not in api_source:
    raise SystemExit("The admin product RPC endpoint was not installed")
if '@GET("rest/v1/products")' in api_source:
    raise SystemExit("A direct GET of the protected products table remains in the Retrofit API")
if 'getAdminProducts("*", "id.asc", range, "items")' in repository_source:
    raise SystemExit("Product synchronization still reads the protected table directly")
if 'productDao.replaceProducts(entities)' not in repository_source:
    raise SystemExit("The existing atomic local-cache replacement was unexpectedly changed")
if 'if (page.size < SupabaseConfig.PAGE_SIZE) break' not in repository_source:
    raise SystemExit("The existing product pagination completion guard was unexpectedly changed")

if 'java.util.UUID.randomUUID().toString()' not in repository_source:
    raise SystemExit("New products must receive a canonical UUID before an insert")
if 'return=minimal' not in repository_source:
    raise SystemExit("Product upsert must not request protected columns in its response")
if 'val persistedProductId = remoteProductId' not in repository_source:
    raise SystemExit("The product save path no longer preserves its client-generated UUID")
if 'Response<Unit>' not in api_source:
    raise SystemExit("The product upsert API must use a minimal response type")

print("PASS: dashboard product synchronization keeps its authenticated paging and cache-preservation behavior.")

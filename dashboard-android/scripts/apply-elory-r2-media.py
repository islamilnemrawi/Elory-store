from pathlib import Path
import os

root = Path(os.environ["PROJECT_DIR"]).resolve()
base = root / "app/src/main/java/com/pinky/dashboard/data/remote"
product_path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/products/ProductEditDialog.kt"
category_path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/categories/CategoriesScreen.kt"
website_path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt"

if "R2MediaUploader" in (base / "SupabaseStorageUploader.kt").read_text(encoding="utf-8"):
    raise SystemExit("R2 media integration already exists; refusing to apply a duplicate patch.")

uploader = r'''package com.pinky.dashboard.data.remote
import android.content.ContentResolver
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.IOException

/** Backward-compatible image uploader backed by Cloudflare R2. */
object SupabaseStorageUploader {
    private const val MAX_IMAGE_DIMENSION = 1600
    private const val WEBP_QUALITY = 82

    suspend fun uploadProductImage(contentResolver: ContentResolver, uri: Uri, productId: String, label: String, permission: String = "products.edit"): String = withContext(Dispatchers.IO) {
        val safeId = productId.replace(Regex("[^A-Za-z0-9_-]"), "_").take(80).ifBlank { "asset" }
        val safeLabel = label.replace(Regex("[^A-Za-z0-9_-]"), "_").take(24).ifBlank { "image" }
        val prefix = when (permission) {
            "products.add", "products.edit" -> "products"
            "categories.manage" -> "categories"
            "offers.manage", "website.manage" -> "site"
            else -> throw SecurityException("صلاحية رفع الوسائط غير معروفة.")
        }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) } ?: throw IOException("تعذر فتح ملف الصورة المحدد.")
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw IOException("ملف الصورة غير صالح.")
        var sample = 1
        while (bounds.outWidth / sample > MAX_IMAGE_DIMENSION * 2 || bounds.outHeight / sample > MAX_IMAGE_DIMENSION * 2) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample; inPreferredConfig = Bitmap.Config.ARGB_8888 }
        val bitmap = contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) } ?: throw IOException("تعذر قراءة الصورة من الهاتف.")
        val scaled = try {
            val max = maxOf(bitmap.width, bitmap.height)
            if (max > MAX_IMAGE_DIMENSION) {
                val factor = MAX_IMAGE_DIMENSION.toFloat() / max
                Bitmap.createScaledBitmap(bitmap, (bitmap.width * factor).toInt().coerceAtLeast(1), (bitmap.height * factor).toInt().coerceAtLeast(1), true).also { if (it !== bitmap) bitmap.recycle() }
            } else bitmap
        } catch (e: Exception) { bitmap.recycle(); throw IOException("تعذر تجهيز الصورة للرفع.", e) }
        val bytes = try {
            ByteArrayOutputStream().use { out ->
                val format = if (android.os.Build.VERSION.SDK_INT >= 30) Bitmap.CompressFormat.WEBP_LOSSY else Bitmap.CompressFormat.WEBP
                if (!scaled.compress(format, WEBP_QUALITY, out)) throw IOException("تعذر ضغط الصورة.")
                out.toByteArray()
            }
        } finally { scaled.recycle() }
        R2MediaUploader.uploadBytes("$prefix/$safeId/${safeLabel}_${java.util.UUID.randomUUID()}.webp", bytes, "image/webp", permission)
    }
}
'''

r2 = r'''package com.pinky.dashboard.data.remote
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Authenticated media transport. R2 credentials never enter the Android app. */
object R2MediaUploader {
    const val BASE_URL = "https://elory-media.islamilnemrawi222.workers.dev"
    private val client = OkHttpClient.Builder().connectTimeout(30, TimeUnit.SECONDS).writeTimeout(120, TimeUnit.SECONDS).readTimeout(60, TimeUnit.SECONDS).build()

    suspend fun uploadBytes(key: String, bytes: ByteArray, contentType: String, permission: String): String =
        uploadRequestBody(key, bytes.toRequestBody(contentType.toMediaType()), contentType, permission)

    suspend fun uploadRequestBody(key: String, body: RequestBody, contentType: String, permission: String): String = withContext(Dispatchers.IO) {
        check(SupabaseClient.hasValidConfiguration) { "إعدادات الاتصال بقاعدة البيانات غير مكتملة." }
        check(SupabaseClient.performTokenRefresh() && !SupabaseClient.accessToken.isNullOrBlank()) { "انتهت جلسة الدخول. سجّل الدخول مرة أخرى قبل رفع الوسائط." }
        require(key.split('/').all { it.matches(Regex("[A-Za-z0-9._-]{1,100}")) }) { "مسار الملف غير صالح." }
        val encodedKey = key.split('/').joinToString("/") { java.net.URLEncoder.encode(it, "UTF-8").replace("+", "%20") }
        val request = Request.Builder().url("$BASE_URL/upload/$encodedKey")
            .header("Authorization", "Bearer ${SupabaseClient.accessToken}")
            .header("X-Elory-Permission", permission)
            .header("Content-Type", contentType)
            .post(body).build()
        client.newCall(request).execute().use { response ->
            val payload = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val message = runCatching { JSONObject(payload).optString("message") }.getOrNull().orEmpty()
                throw IOException(message.ifBlank { "فشل رفع الملف إلى التخزين السحابي (HTTP ${response.code})." })
            }
            JSONObject(payload).optString("url").takeIf { it.startsWith("https://") }
                ?: throw IOException("تم رفع الملف لكن لم يصل رابط صالح من خدمة التخزين.")
        }
    }
}
'''

(base / "SupabaseStorageUploader.kt").write_text(uploader, encoding="utf-8")
(base / "R2MediaUploader.kt").write_text(r2, encoding="utf-8")

hero_path = base / "HeroAdMediaUploader.kt"
hero = hero_path.read_text(encoding="utf-8")
start = hero.index("        val response = SupabaseClient.service.uploadStorageFile(")
end = hero.index("\n    }\n}", start)
hero = hero[:start] + '''        R2MediaUploader.uploadRequestBody(
            key = "hero/$fileName",
            body = body,
            contentType = mimeType,
            permission = "website.manage"
        )''' + hero[end:]
hero_path.write_text(hero, encoding="utf-8")

product = product_path.read_text(encoding="utf-8")
product = product.replace(
    'SupabaseStorageUploader.uploadProductImage(context.contentResolver, uri, productId, "main")',
    'SupabaseStorageUploader.uploadProductImage(context.contentResolver, uri, productId, "main", if (initialProduct == null) "products.add" else "products.edit")'
)
product = product.replace(
    'SupabaseStorageUploader.uploadProductImage(context.contentResolver, uri, productId, "gallery_${index + 1}")',
    'SupabaseStorageUploader.uploadProductImage(context.contentResolver, uri, productId, "gallery_${index + 1}", if (initialProduct == null) "products.add" else "products.edit")'
)
product_path.write_text(product, encoding="utf-8")

category = category_path.read_text(encoding="utf-8")
category = category.replace('label = "category"\n                    )', 'label = "category",\n                        permission = "categories.manage"\n                    )')
category_path.write_text(category, encoding="utf-8")

website = website_path.read_text(encoding="utf-8")
website = website.replace('label = "website"\n                    )', 'label = "website",\n                        permission = "website.manage"\n                    )')
website_path.write_text(website, encoding="utf-8")

print("PASS: R2 uploads wired for product, category, website and hero media.")

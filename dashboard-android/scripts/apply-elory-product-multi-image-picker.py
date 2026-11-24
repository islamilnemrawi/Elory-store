from pathlib import Path
import os
root = Path(os.environ["PROJECT_DIR"]).resolve()
p = root / "app/src/main/java/com/pinky/dashboard/ui/screens/products/ProductEditDialog.kt"
u = root / "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseStorageUploader.kt"
s = p.read_text(encoding="utf-8")
old = '''    // Media Picker States
    var selectedMainImageUri by remember { mutableStateOf<Uri?>(null) }
    var selectedGalleryUris by remember { mutableStateOf<List<Uri>>(emptyList()) }
    var isSaving by remember { mutableStateOf(false) }
    var uploadError by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    // Photo pickers
    val mainImageLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia()
    ) { uri ->
        if (uri != null) {
            selectedMainImageUri = uri
            uploadError = null
        }
    }

    val galleryLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickMultipleVisualMedia(maxItems = 5)
    ) { uris ->
        if (uris.isNotEmpty()) {
            selectedGalleryUris = uris
        }
    }
'''
new = '''    var selectedProductImageUris by remember { mutableStateOf<List<Uri>>(emptyList()) }
    var isSaving by remember { mutableStateOf(false) }
    var uploadError by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val productImagesLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickMultipleVisualMedia(maxItems = 20)
    ) { uris ->
        if (uris.isNotEmpty()) {
            selectedProductImageUris = (selectedProductImageUris + uris).distinct().take(20)
            uploadError = null
        }
    }
'''
if s.count(old) != 1: raise SystemExit("Picker state mismatch.")
s = s.replace(old, new, 1)
a = '                    // Image picker & Gallery picker (R2 Ready Architecture)'
b = '                    // Product Variants management'
if s.count(a) != 1 or s.count(b) != 1: raise SystemExit("Image UI boundaries ambiguous.")
i, j = s.index(a), s.index(b)
ui = '''                    item {
                        Card(shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.15f)), border = CardDefaults.outlinedCardBorder()) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Text("صور المنتج", style = MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold), color = PinkPrimary)
                                Text("اختَر حتى 20 صورة من معرض الهاتف. الصورة الأولى ستكون الرئيسية وباقي الصور ستظهر في معرض المنتج.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                Button(onClick = { productImagesLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp), colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))) {
                                    Icon(Icons.Outlined.Collections, contentDescription = null, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(8.dp))
                                    Text(if (selectedProductImageUris.isEmpty()) "اختيار صور من معرض الهاتف" else "إضافة صور أخرى (" + selectedProductImageUris.size + "/20)", fontWeight = FontWeight.Bold)
                                }
                                if (selectedProductImageUris.isNotEmpty()) {
                                    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                                        items(selectedProductImageUris) { uri ->
                                            Box(Modifier.size(76.dp).clip(RoundedCornerShape(10.dp)).border(1.dp, PinkPrimary, RoundedCornerShape(10.dp))) {
                                                AsyncImage(model = uri, contentDescription = "صورة محددة للمنتج", contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                                                Surface(Modifier.align(Alignment.TopEnd).padding(3.dp), shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.surface.copy(alpha = 0.92f)) {
                                                    IconButton(onClick = { selectedProductImageUris = selectedProductImageUris.filterNot { it == uri } }, modifier = Modifier.size(25.dp)) {
                                                        Icon(Icons.Outlined.Close, contentDescription = "إزالة الصورة", tint = MaterialTheme.colorScheme.error, modifier = Modifier.size(16.dp))
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    Text(selectedProductImageUris.size.toString() + " صورة محددة — أول صورة هي الغلاف", style = MaterialTheme.typography.labelSmall, color = PinkPrimary)
                                } else if (imageUrl.isNotBlank()) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                        AsyncImage(model = imageUrl, contentDescription = "الصورة الرئيسية الحالية", contentScale = ContentScale.Crop, modifier = Modifier.size(64.dp).clip(RoundedCornerShape(8.dp)))
                                        Text("الصورة الرئيسية الحالية", style = MaterialTheme.typography.labelSmall)
                                    }
                                }
                            }
                        }
                    }

'''
s = s[:i] + ui + s[j:]
old_save = '''                                        val finalImageUrl = selectedMainImageUri?.let { uri ->
                                            SupabaseStorageUploader.uploadProductImage(context.contentResolver, uri, productId, "main", if (initialProduct == null) "products.add" else "products.edit")
                                        } ?: imageUrl
                                        val finalGallery = if (selectedGalleryUris.isNotEmpty()) {
                                            selectedGalleryUris.mapIndexed { index, uri ->
                                                SupabaseStorageUploader.uploadProductImage(context.contentResolver, uri, productId, "gallery_INDEX", if (initialProduct == null) "products.add" else "products.edit")
                                            }
                                        } else {
                                            initialProduct?.gallery ?: emptyList()
                                        }
'''
old_save = old_save.replace("gallery_INDEX", "gallery_" + chr(36) + "{index + 1}")
new_save = '''                                        val uploadedProductImages = selectedProductImageUris.mapIndexed { index, uri ->
                                            try {
                                                SupabaseStorageUploader.uploadProductImage(context.contentResolver, uri, productId, if (index == 0) "cover" else "gallery_" + index, if (initialProduct == null) "products.add" else "products.edit")
                                            } catch (error: Exception) {
                                                throw java.io.IOException("فشل رفع الصورة رقم " + (index + 1) + ": " + (error.localizedMessage ?: "تعذر قراءة ملف الصورة"), error)
                                            }
                                        }
                                        val finalImageUrl = uploadedProductImages.firstOrNull() ?: imageUrl
                                        val finalGallery = if (uploadedProductImages.isNotEmpty()) {
                                            val previousCover = initialProduct?.imageUrl?.takeIf { it.isNotBlank() && it != finalImageUrl }
                                            (initialProduct?.gallery.orEmpty() + listOfNotNull(previousCover) + uploadedProductImages.drop(1)).distinct()
                                        } else initialProduct?.gallery ?: emptyList()
'''
if s.count(old_save) != 1: raise SystemExit("Product upload/save block mismatch.")
s = s.replace(old_save, new_save, 1)
for x in ("selectedMainImageUri", "selectedGalleryUris", "mainImageLauncher", "galleryLauncher"):
    if x in s: raise SystemExit("Legacy picker still referenced: " + x)
if "PickVisualMedia()" in s: raise SystemExit("Single-image picker still exists.")
p.write_text(s, encoding="utf-8")

uploader = r'''package com.pinky.dashboard.data.remote
import android.content.ContentResolver
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.IOException
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
        val bitmap = decodeSelectedImage(contentResolver, uri)
        val scaled = try {
            val longest = maxOf(bitmap.width, bitmap.height)
            if (longest > MAX_IMAGE_DIMENSION) {
                val factor = MAX_IMAGE_DIMENSION.toFloat() / longest.toFloat()
                Bitmap.createScaledBitmap(bitmap, (bitmap.width * factor).toInt().coerceAtLeast(1), (bitmap.height * factor).toInt().coerceAtLeast(1), true).also { if (it !== bitmap) bitmap.recycle() }
            } else bitmap
        } catch (error: Exception) { bitmap.recycle(); throw IOException("تعذر تجهيز الصورة للرفع. جرّب صورة أخرى بصيغة JPG أو PNG.", error) }
        val bytes = try {
            ByteArrayOutputStream().use { output ->
                val format = if (Build.VERSION.SDK_INT >= 30) Bitmap.CompressFormat.WEBP_LOSSY else Bitmap.CompressFormat.WEBP
                if (!scaled.compress(format, WEBP_QUALITY, output)) throw IOException("تعذر ضغط الصورة.")
                output.toByteArray()
            }
        } finally { scaled.recycle() }
        if (bytes.isEmpty()) throw IOException("ملف الصورة فارغ أو غير قابل للقراءة.")
        R2MediaUploader.uploadBytes("$prefix/$safeId/" + safeLabel + "_" + java.util.UUID.randomUUID() + ".webp", bytes, "image/webp", permission)
    }
    private fun decodeSelectedImage(resolver: ContentResolver, uri: Uri): Bitmap {
        val mime = runCatching { resolver.getType(uri) }.getOrNull() ?: "غير معروف"
        if (uri.scheme != "content" && uri.scheme != "file") throw IOException("مصدر الصورة غير مدعوم. اختَر الصورة من معرض الهاتف.")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val decoded = runCatching {
                ImageDecoder.decodeBitmap(ImageDecoder.createSource(resolver, uri)) { decoder, info, _ ->
                    decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                    decoder.isMutableRequired = true
                    val longest = maxOf(info.size.width, info.size.height)
                    if (longest > MAX_IMAGE_DIMENSION * 2) {
                        val factor = (MAX_IMAGE_DIMENSION * 2).toFloat() / longest.toFloat()
                        decoder.setTargetSize((info.size.width * factor).toInt().coerceAtLeast(1), (info.size.height * factor).toInt().coerceAtLeast(1))
                    }
                }
            }.getOrNull()
            if (decoded != null) return decoded
        }
        try {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) } ?: throw IOException("لم يستطع الهاتف فتح ملف الصورة.")
            if (bounds.outWidth <= 0 || bounds.outHeight <= 0) throw IOException("صيغة الصورة غير مدعومة أو الملف تالف.")
            var sample = 1
            while (bounds.outWidth / sample > MAX_IMAGE_DIMENSION * 2 || bounds.outHeight / sample > MAX_IMAGE_DIMENSION * 2) sample *= 2
            val options = BitmapFactory.Options().apply { inSampleSize = sample; inPreferredConfig = Bitmap.Config.ARGB_8888 }
            return resolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, options) } ?: throw IOException("تعذر فك ترميز الصورة من معرض الهاتف.")
        } catch (error: SecurityException) {
            throw IOException("انتهى إذن قراءة الصورة. أعد اختيارها من معرض الهاتف ثم حاول الحفظ.", error)
        } catch (error: IOException) {
            throw IOException("تعذر قراءة الصورة (النوع: " + mime + "). تأكد أن الملف صورة سليمة ومتاحة على الهاتف.", error)
        } catch (error: Exception) {
            throw IOException("تعذر فتح الصورة (النوع: " + mime + "): " + (error.localizedMessage ?: "خطأ غير معروف"), error)
        }
    }
}
'''
u.write_text(uploader, encoding="utf-8")
assert p.read_text(encoding="utf-8").count("PickMultipleVisualMedia(maxItems = 20)") == 1
assert "PickVisualMedia()" not in p.read_text(encoding="utf-8")
assert "selectedProductImageUris = (selectedProductImageUris + uris).distinct().take(20)" in p.read_text(encoding="utf-8")
assert "uploadedProductImages.firstOrNull()" in p.read_text(encoding="utf-8")
assert "ImageDecoder.decodeBitmap" in u.read_text(encoding="utf-8")
assert "R2MediaUploader.uploadBytes(" in u.read_text(encoding="utf-8")
print("PASS: single multi-image picker, append/remove previews, first-image cover, gallery save, and modern image decoding.")

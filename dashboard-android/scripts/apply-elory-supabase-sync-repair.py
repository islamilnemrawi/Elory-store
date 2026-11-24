from pathlib import Path
import os
import re

PROJECT = Path(os.environ["PROJECT_DIR"]).resolve()


def read(relative: str) -> str:
    path = PROJECT / relative
    if not path.is_file():
        raise SystemExit(f"Missing required source file: {relative}")
    return path.read_text(encoding="utf-8")


def write(relative: str, source: str) -> None:
    path = PROJECT / relative
    path.write_text(source, encoding="utf-8")


# 1) Use the shared compressed WebP uploader for category images.
category_path = "app/src/main/java/com/pinky/dashboard/ui/screens/categories/CategoriesScreen.kt"
category = read(category_path)
if "SupabaseStorageUploader.uploadProductImage" not in category:
    anchor = "val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }"
    if category.count(anchor) != 1:
        raise SystemExit("Category image upload anchor is missing or duplicated")
    anchor_pos = category.index(anchor)
    try_start = category.rfind("                try {", 0, anchor_pos)
    catch_start = category.find("                } catch (e: Exception) {", anchor_pos)
    if try_start < 0 or catch_start < 0:
        raise SystemExit("Could not locate the category image upload try/catch block")
    replacement = '''                try {
                    val uploadedUrl = SupabaseStorageUploader.uploadProductImage(
                        contentResolver = context.contentResolver,
                        uri = uri,
                        productId = category?.id ?: "new-category",
                        label = "category"
                    )
                    imageUrl = uploadedUrl
                    uploadSuccess = true
'''
    category = category[:try_start] + replacement + category[catch_start:]

category = category.replace(
    "import com.pinky.dashboard.data.remote.SupabaseClient\n",
    "",
)
category = category.replace(
    "import okhttp3.MediaType.Companion.toMediaTypeOrNull\n",
    "",
)
if "import com.pinky.dashboard.data.remote.SupabaseStorageUploader\n" not in category:
    import_anchor = "import com.pinky.dashboard.domain.model.Category\n"
    if category.count(import_anchor) != 1:
        raise SystemExit("Category import anchor is missing or duplicated")
    category = category.replace(
        import_anchor,
        "import com.pinky.dashboard.data.remote.SupabaseStorageUploader\n" + import_anchor,
        1,
    )
category = category.replace(
    'Text("صيغة JPG أو PNG", fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)',
    'Text("يتم ضغط الصورة تلقائيًا قبل رفعها", fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)',
)

# Preview the compact embedded JPEG category images without requiring Coil data-URI support.
package_anchor = "package com.pinky.dashboard.ui.screens.categories\n\n"
if "import android.graphics.BitmapFactory\n" not in category:
    if category.count(package_anchor) != 1:
        raise SystemExit("Category package anchor is missing or duplicated")
    category = category.replace(
        package_anchor,
        package_anchor
        + "import android.graphics.BitmapFactory\n"
        + "import android.util.Base64\n"
        + "import androidx.compose.foundation.Image\n"
        + "import androidx.compose.ui.graphics.asImageBitmap\n",
        1,
    )
context_anchor = "    val context = LocalContext.current\n"
bitmap_state = """    val storedImageBitmap = remember(imageUrl) {
        if (imageUrl.startsWith("data:image/") && ";base64," in imageUrl) {
            runCatching {
                val encoded = imageUrl.substringAfter(";base64,")
                val bytes = Base64.decode(encoded, Base64.DEFAULT)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
            }.getOrNull()
        } else null
    }
"""
if "val storedImageBitmap = remember(imageUrl)" not in category:
    if category.count(context_anchor) != 1:
        raise SystemExit("Category dialog context anchor is missing or duplicated")
    category = category.replace(context_anchor, context_anchor + bitmap_state, 1)
image_block_old = """                            AsyncImage(
                                model = selectedImageUri ?: imageUrl,
                                contentDescription = null,
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.fillMaxSize()
                            )"""
image_block_new = """                            if (selectedImageUri != null) {
                                AsyncImage(
                                    model = selectedImageUri,
                                    contentDescription = null,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.fillMaxSize()
                                )
                            } else if (storedImageBitmap != null) {
                                Image(
                                    bitmap = storedImageBitmap,
                                    contentDescription = null,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.fillMaxSize()
                                )
                            } else {
                                AsyncImage(
                                    model = imageUrl,
                                    contentDescription = null,
                                    contentScale = ContentScale.Crop,
                                    modifier = Modifier.fillMaxSize()
                                )
                            }"""
if image_block_old in category:
    category = category.replace(image_block_old,image_block_new,1)
elif "storedImageBitmap != null" not in category:
    raise SystemExit("Category image preview block is missing or duplicated")
if "SupabaseStorageUploader.uploadProductImage" not in category or "uploadStorageFile(" in category:
    raise SystemExit("Category image upload did not switch to the shared uploader")
write(category_path, category)
print("PASS: category images use compressed, uniquely named WebP uploads")

# 2) Make the secondary Supabase reads awaited and report failures to the sync UI.
view_model_path = "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
source = read(view_model_path)
function_start = source.find("    private fun syncRemainingSupabaseData() {")
if function_start < 0:
    raise SystemExit("Could not locate syncRemainingSupabaseData()")
function_header = "    private fun syncRemainingSupabaseData() {"
# The patched ViewModel implementation is the final method and owns one launch block.
# Locate its final two closing braces explicitly; nested method braces use deeper indentation.
function_end_marker = "\n        }\n    }"
function_end_position = source.find(function_end_marker, function_start)
if function_end_position < 0:
    raise SystemExit("Could not locate the end of syncRemainingSupabaseData()")
function_end = function_end_position + len(function_end_marker)

block = source[function_start:function_end]

old_header = "    private fun syncRemainingSupabaseData() {\n        viewModelScope.launch {\n"
new_header = "    private suspend fun syncRemainingSupabaseData(): List<String> {\n        val errors = mutableListOf<String>()\n"
if block.count(old_header) != 1:
    raise SystemExit("Unexpected syncRemainingSupabaseData() wrapper")
block = block.replace(old_header, new_header, 1)

# Surface unsuccessful HTTP responses regardless of local variable names or blank lines.
response_methods = [
    ("getCoupons", "الكوبونات"),
    ("getStaffProfiles", "الموظفون"),
]
# Prime reads are already routed through the schema-safe admin RPC by the
# operations patch; accept that implementation instead of requiring the legacy table DTO.
if "getPrimeSubscriptions()" not in block and "refreshPrimeSubscribers()" not in block:
    raise SystemExit("Missing Prime subscription read (legacy REST or schema-safe RPC)")
for method, label in response_methods:
    call_pattern = re.compile(
        r"(?m)^([ \t]*)val[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*SupabaseClient\.service\."
        + re.escape(method) + r"\(\)"
    )
    call_matches = list(call_pattern.finditer(block))
    if len(call_matches) != 1:
        raise SystemExit("Missing or duplicated Supabase read call: " + method)
    call_match = call_matches[0]
    variable = call_match.group(2)
    if_pattern = re.compile(
        r"(?m)^([ \t]*)if[ \t]*\([ \t]*" + re.escape(variable) + r"\.isSuccessful[ \t]*\)[ \t]*\{"
    )
    if_match = if_pattern.search(block, call_match.end())
    if if_match is None or if_match.start() - call_match.end() > 700:
        raise SystemExit("Missing success branch for Supabase read: " + method)
    indent = if_match.group(1)
    check = (
        'if (!' + variable + '.isSuccessful) errors.add("' + label
        + ': HTTP ${' + variable + '.code()}")\n' + indent
    )
    block = block[:if_match.start()] + check + block[if_match.start():]

settings_call = re.compile(
    r"(?m)^([ \t]*)val[ \t]+settingsResponse[ \t]*=[ \t]*SupabaseClient\.service\.getStoreSettings\(\)"
)
custom_call = re.compile(
    r"(?m)^([ \t]*)val[ \t]+customizationsResponse[ \t]*=[ \t]*SupabaseClient\.service\.getSiteCustomizations\(\)"
)
settings_matches = list(settings_call.finditer(block))
custom_matches = list(custom_call.finditer(block))
if len(settings_matches) != 1 or len(custom_matches) != 1:
    raise SystemExit("Missing or duplicated store/site settings read calls")
for variable, pattern, label in [
    ("settingsResponse", settings_call, "إعدادات المتجر"),
    ("customizationsResponse", custom_call, "تخصيصات الموقع"),
]:
    match = list(pattern.finditer(block))[0]
    line_end = block.find("\n", match.end())
    if line_end < 0:
        raise SystemExit("Could not locate settings response line ending: " + variable)
    indent = match.group(1)
    check = '\n' + indent + 'if (!' + variable + '.isSuccessful) errors.add("' + label + ': HTTP ${' + variable + '.code()}")'
    block = block[:line_end] + check + block[line_end:]

# Keep each read independent: a failed section reports its own error and does not cancel the other reads.
catch_sections = [
    ("// Fetch Coupons", "الكوبونات"),
    ("// Fetch Staff Profiles", "الموظفون"),
    ("// Fetch Store Settings and Site Customizations", "إعدادات الموقع"),
]
for marker, label in catch_sections:
    marker_pos = block.find(marker)
    catch_pos = block.find("e.printStackTrace()", marker_pos + len(marker)) if marker_pos >= 0 else -1
    next_marker_positions = [block.find(next_marker, marker_pos + len(marker)) for next_marker, _ in catch_sections if block.find(next_marker, marker_pos + len(marker)) >= 0]
    next_marker = min(next_marker_positions) if next_marker_positions else len(block)
    if marker_pos < 0 or catch_pos < 0 or catch_pos > next_marker:
        raise SystemExit("Expected Supabase read catch block is missing: " + label)
    replacement = (
        'android.util.Log.e("SupabaseSync", "' + label + ' fetch failed", e)\n'
        '                errors.add(if (isNetworkException(e)) "NETWORK:' + label + '" '
        'else "' + label + ': ${e.message ?: e.javaClass.simpleName}")'
    )
    block = block[:catch_pos] + replacement + block[catch_pos + len("e.printStackTrace()"):]

if not block.endswith("        }\n    }"):
    raise SystemExit("Unexpected end of syncRemainingSupabaseData()")
block = block[:-len("        }\n    }")] + "        return errors\n    }"
if "viewModelScope.launch" in block:
    raise SystemExit("syncRemainingSupabaseData() still launches an unawaited coroutine")

source = source[:function_start] + block + source[function_end:]

old_sync_call = '''                // Sync remaining in-memory states (Coupons, Prime, Staff, Settings, Cust, Devices)
                try {
                    syncRemainingSupabaseData()
                } catch (e: Exception) {
                    android.util.Log.e("SupabaseSync", "Error syncing remaining in-memory data: ${e.message}")
                }

                val errors = mutableListOf<String>()
                var hasNetworkError = false
'''
new_sync_call = '''                val errors = mutableListOf<String>()
                var hasNetworkError = false

                // Wait for all secondary Supabase reads before marking synchronization complete.
                val remainingSyncErrors = syncRemainingSupabaseData()
                remainingSyncErrors.forEach { issue ->
                    if (issue.startsWith("NETWORK:")) {
                        hasNetworkError = true
                    } else {
                        errors.add(issue)
                    }
                }
'''
if source.count(old_sync_call) != 1:
    raise SystemExit("Could not locate centralized sync call site")
source = source.replace(old_sync_call, new_sync_call, 1)

if source.count("private suspend fun syncRemainingSupabaseData(): List<String>") != 1:
    raise SystemExit("Suspend sync function verification failed")
if "val remainingSyncErrors = syncRemainingSupabaseData()" not in source:
    raise SystemExit("Awaited sync call verification failed")
write(view_model_path, source)
print("PASS: secondary Supabase reads are awaited and HTTP/network failures reach syncError")
print("All Supabase sync repair checks passed.")

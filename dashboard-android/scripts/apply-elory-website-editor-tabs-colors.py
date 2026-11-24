#!/usr/bin/env python3
"""Organize the website editor into section tabs and replace fixed HEX inputs with a free color wheel."""
from pathlib import Path
import os, re

root = Path(os.environ.get("PROJECT_DIR", "")).resolve()
if not root.is_dir():
    raise SystemExit("PROJECT_DIR is missing or invalid")
file = root / "app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt"
if not file.exists():
    raise SystemExit(f"Website editor source not found: {file}")
text = file.read_text(encoding="utf-8")

def matching_end(source, start, left="{", right="}"):
    depth, i, state, quote = 0, start, "normal", ""
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if state == "line":
            if ch == "\n": state = "normal"
        elif state == "block":
            if ch == "*" and nxt == "/": state = "normal"; i += 1
        elif state == "string":
            if ch == "\\": i += 1
            elif ch == quote: state = "normal"
        else:
            if ch == "/" and nxt == "/": state = "line"; i += 1
            elif ch == "/" and nxt == "*": state = "block"; i += 1
            elif ch in ('"', "'"): state = "string"; quote = ch
            elif ch == left:
                depth += 1
            elif ch == right:
                depth -= 1
                if depth == 0: return i
        i += 1
    raise RuntimeError(f"Unbalanced Kotlin block at {start}")

def wrap_card(source, number, section):
    marker = f"// Card {number}:"
    start = source.find(marker)
    if start < 0: raise RuntimeError(f"Missing website editor card {number}")
    item = source.find("item {", start)
    if item < 0: raise RuntimeError(f"Missing LazyColumn item for card {number}")
    if f"selectedEditorSection == {section}" in source[max(0,item-100):item]:
        return source
    brace = source.find("{", item)
    end = matching_end(source, brace)
    block = source[item:end+1]
    wrapped = f"if (selectedEditorSection == {section}) {{\n                        {block}\n                    }}"
    return source[:item] + wrapped + source[end+1:]

# Add the section tab state next to the existing editor/preview tab state.
if "selectedEditorSection" not in text:
    m = re.search(r"var selectedTab by remember\s*\{[^}]*\}", text)
    if not m:
        raise RuntimeError("Could not find the existing editor/preview tab state")
    text = text[:m.end()] + "\n    var selectedEditorSection by remember { mutableIntStateOf(0) }" + text[m.end():]

# Five focused groups; the preview tab stays exactly as it is.
tab_marker = "if (selectedTab == 0)"
tab_pos = text.find(tab_marker)
if tab_pos < 0: raise RuntimeError("Could not find editor/preview content switch")
if "ScrollableTabRow(selectedTabIndex = selectedEditorSection" not in text:
    tabs = '''if (selectedTab == 0) {
                ScrollableTabRow(
                    selectedTabIndex = selectedEditorSection,
                    edgePadding = 8.dp
                ) {
                    listOf(
                        "الرأس والتنقل",
                        "البنرات",
                        "الأقسام والمنتجات",
                        "Prime والمميزات",
                        "المعرض والهوية"
                    ).forEachIndexed { index, title ->
                        Tab(
                            selected = selectedEditorSection == index,
                            onClick = { selectedEditorSection = index },
                            text = { Text(title, maxLines = 1) }
                        )
                    }
                }
            }

            '''
    text = text[:tab_pos] + tabs + text[tab_pos:]

# Group the existing 11 cards without rebuilding or duplicating their forms.
groups = {1:0, 2:0, 3:0, 4:1, 5:2, 6:2, 7:3, 8:3, 9:4, 10:4, 11:4}
for number, section in groups.items():
    text = wrap_card(text, number, section)

# Place global controls once and section ordering with categories/products.
editor_start = text.find("// Editor Sections List")
if editor_start < 0:
    editor_start = text.find("ScrollableTabRow(selectedTabIndex = selectedEditorSection")
if editor_start < 0:
    raise RuntimeError("Could not locate the website editor section container")

store_state_pos = text.find("المتجر مفتوح للزوار", editor_start)
if store_state_pos < 0:
    store_state_pos = text.find("Switch(checked = config.isStoreOpen", editor_start)
if store_state_pos >= 0:
    store_item = text.rfind("item {", editor_start, store_state_pos)
    if store_item < 0:
        raise RuntimeError("Found store status but not its LazyColumn item")
    store_brace = text.find("{", store_item)
    store_end = matching_end(text, store_brace)
    if "selectedEditorSection == 0" not in text[max(editor_start, store_item - 220):store_item]:
        store_block = text[store_item:store_end + 1]
        text = text[:store_item] + "if (selectedEditorSection == 0) {" + chr(10) + store_block + chr(10) + "}" + text[store_end + 1:]

sort_title = text.find('title = "ترتيب وظهور أقسام الصفحة"', editor_start)
if sort_title < 0:
    raise RuntimeError("Could not locate the section-ordering card")
sort_item = text.rfind("item {", editor_start, sort_title)
if sort_item < 0:
    raise RuntimeError("Found section-order title but not its LazyColumn item")
sort_brace = text.find("{", sort_item)
sort_end = matching_end(text, sort_brace)
if "selectedEditorSection == 2" not in text[max(editor_start, sort_item - 220):sort_item]:
    sort_block = text[sort_item:sort_end + 1]
    text = text[:sort_item] + "if (selectedEditorSection == 2) {" + chr(10) + sort_block + chr(10) + "}" + text[sort_end + 1:]

text = text.replace(
    "var selectedEditorSection by remember { mutableIntStateOf(0) } // 0 = Editor, 1 = Live Preview Mockup",
    "var selectedEditorSection by remember { mutableIntStateOf(0) } // 0 = Header, 1 = Banners, 2 = Categories, 3 = Prime visibility, 4 = Gallery and identity"
)

# Prime pricing, duration, discount and shipping benefits are managed in the Prime area.
# In Website Editor keep only the website visibility switch to avoid duplicate controls.
prime_marker = "// Card 7: Elory Prime"
prime_start = text.find(prime_marker)
prime_item = text.find("item {", prime_start)
prime_brace = text.find("{", prime_item)
prime_end = matching_end(text, prime_brace)
prime_block = text[prime_item:prime_end+1]
prime_block = prime_block.replace(
    'description = "تخصيص الباقات والأسعار والمزايا الحصرية للأعضاء"',
    'description = "إظهار أو إخفاء قسم Prime في الموقع؛ الأسعار والمزايا التشغيلية تُدار من قسم Prime"'
)
prime_block = prime_block.replace("SectionCard(", "PrimeVisibilityCard(", 1)
prime_block = re.sub(r"^\s*onClick\s*=\s*\{.*?\}\s*,?\s*$", "", prime_block, flags=re.MULTILINE)
text = text[:prime_item] + prime_block + text[prime_end+1:]

# Replace the five free-form HEX text fields with a real hue wheel + saturation/brightness picker.
def replace_color_field(source, field, label, weighted=False):
    target = f"value = config.{field}"
    pos = source.find(target)
    if pos < 0:
        raise RuntimeError(f"Color field {field} not found")
    start = source.rfind("OutlinedTextField(", 0, pos)
    if start < 0:
        raise RuntimeError(f"OutlinedTextField wrapper for {field} not found")
    op = source.find("(", start)
    end = matching_end(source, op, "(", ")")
    modifier = ", modifier = Modifier.weight(1f)" if weighted else ""
    replacement = (
        f'ColorPickerField(label = "{label}", colorHex = config.{field}, '
        f'onColorChange = {{ onUpdate(config.copy({field} = it)) }}{modifier})'
    )
    return source[:start] + replacement + source[end+1:]

for field, label, weighted in (
    ("announcementBgColor", "لون خلفية الشريط الإعلاني", True),
    ("announcementTextColor", "لون نص الشريط الإعلاني", True),
    ("headerBgColor", "لون خلفية الهيدر", True),
    ("headerIconsColor", "لون أيقونات الهيدر", True),
    ("primaryColorHex", "لون الهوية الأساسي", False),
):
    text = replace_color_field(text, field, label, weighted)

# Import the drawing and pointer APIs required by the wheel.
imports = [
    "import androidx.compose.foundation.Canvas",
    "import androidx.compose.foundation.gestures.detectTapGestures",
    "import androidx.compose.foundation.gestures.detectDragGestures",
    "import androidx.compose.ui.geometry.Offset",
    "import androidx.compose.ui.geometry.Size",
    "import androidx.compose.ui.graphics.drawscope.Stroke",
    "import androidx.compose.ui.input.pointer.pointerInput",
    "import kotlin.math.atan2",
]
for line in imports:
    if line not in text:
        text = text.replace("package com.pinky.dashboard.ui.screens.website", "package com.pinky.dashboard.ui.screens.website\n\n" + line, 1)

if "fun ColorPickerField(" not in text:
    picker = r'''
    
@Composable
private fun ColorPickerField(
    label: String,
    colorHex: String,
    onColorChange: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val initialHsv = remember(colorHex) {
        val raw = colorHex.trim().let { if (it.startsWith("#")) it else "#$it" }
        val parsed = runCatching { android.graphics.Color.parseColor(raw) }
            .getOrDefault(android.graphics.Color.WHITE)
        FloatArray(3).also { android.graphics.Color.colorToHSV(parsed, it) }
    }
    var hue by remember(colorHex) { mutableStateOf(initialHsv[0]) }
    var saturation by remember(colorHex) { mutableStateOf(initialHsv[1]) }
    var brightness by remember(colorHex) { mutableStateOf(initialHsv[2]) }
    var showPicker by remember { mutableStateOf(false) }
    val selectedColor = android.graphics.Color.HSVToColor(floatArrayOf(hue, saturation, brightness))
    val selectedHex = "#%06X".format(0xFFFFFF and selectedColor)

    Row(
        modifier = modifier
            .fillMaxWidth()
            .clickable { showPicker = true }
            .padding(vertical = 10.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            Text(selectedHex, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Box(
            modifier = Modifier
                .size(34.dp)
                .background(androidx.compose.ui.graphics.Color(selectedColor))
        )
        Spacer(modifier = Modifier.width(8.dp))
        TextButton(onClick = { showPicker = true }) { Text("اختيار") }
    }

    if (showPicker) {
        AlertDialog(
            onDismissRequest = { showPicker = false },
            title = { Text(label) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("اختار أي درجة من عجلة الألوان، ثم اضبط التشبع والإضاءة.")
                    Canvas(
                        modifier = Modifier
                            .size(210.dp)
                            .pointerInput(Unit) {
                                detectTapGestures { offset ->
                                    val cx = size.width / 2f
                                    val cy = size.height / 2f
                                    val degrees = Math.toDegrees(atan2((offset.y - cy).toDouble(), (offset.x - cx).toDouble())).toFloat()
                                    hue = (degrees + 360f) % 360f
                                }
                            }
                            .pointerInput(Unit) {
                                detectDragGestures { change, _ ->
                                    val cx = size.width / 2f
                                    val cy = size.height / 2f
                                    val degrees = Math.toDegrees(atan2((change.position.y - cy).toDouble(), (change.position.x - cx).toDouble())).toFloat()
                                    hue = (degrees + 360f) % 360f
                                }
                            }
                    ) {
                        val stroke = 26.dp.toPx()
                        val arcSize = Size(size.width - stroke, size.height - stroke)
                        val origin = Offset(stroke / 2f, stroke / 2f)
                        for (degree in 0 until 360 step 3) {
                            drawArc(
                                color = androidx.compose.ui.graphics.Color(
                                    android.graphics.Color.HSVToColor(floatArrayOf(degree.toFloat(), 1f, 1f))
                                ),
                                startAngle = degree.toFloat(),
                                sweepAngle = 3.4f,
                                useCenter = false,
                                topLeft = origin,
                                size = arcSize,
                                style = Stroke(width = stroke)
                            )
                        }
                    }
                    Text("التشبع")
                    Slider(value = saturation, onValueChange = { saturation = it }, valueRange = 0f..1f)
                    Text("الإضاءة")
                    Slider(value = brightness, onValueChange = { brightness = it }, valueRange = 0f..1f)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(30.dp).background(androidx.compose.ui.graphics.Color(selectedColor)))
                        Spacer(Modifier.width(10.dp))
                        Text(selectedHex, style = MaterialTheme.typography.titleSmall)
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    onColorChange(selectedHex)
                    showPicker = false
                }) { Text("اعتماد اللون") }
            },
            dismissButton = {
                TextButton(onClick = { showPicker = false }) { Text("إلغاء") }
            }
        )
    }
}
'''
    text += picker

if "private fun PrimeVisibilityCard(" not in text:
    text += "\n@Composable\nprivate fun PrimeVisibilityCard(\n    title: String,\n    description: String,\n    icon: androidx.compose.ui.graphics.vector.ImageVector,\n    isActive: Boolean,\n    onToggleActive: ((Boolean) -> Unit)?\n) {\n    Card(\n        modifier = Modifier.fillMaxWidth(),\n        shape = RoundedCornerShape(12.dp),\n        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),\n        border = CardDefaults.outlinedCardBorder()\n    ) {\n        Row(\n            modifier = Modifier.fillMaxWidth().padding(14.dp),\n            verticalAlignment = Alignment.CenterVertically,\n            horizontalArrangement = Arrangement.spacedBy(12.dp)\n        ) {\n            Icon(icon, contentDescription = null, tint = PinkPrimary, modifier = Modifier.size(28.dp))\n            Column(Modifier.weight(1f)) {\n                Text(title, fontWeight = FontWeight.Bold)\n                Text(description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)\n            }\n            onToggleActive?.let { callback ->\n                Switch(checked = isActive, onCheckedChange = callback)\n            }\n        }\n    }\n}\n"

file.write_text(text, encoding="utf-8")

# General site saves must not be blocked by unrelated Prime operational values.
vm_file = root / "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
if not vm_file.exists():
    raise SystemExit(f"ViewModel source not found: {vm_file}")
vm = vm_file.read_text(encoding="utf-8")
update_start = vm.find("    fun updateWebsiteConfig(config: WebsiteConfig) {")
if update_start < 0:
    raise SystemExit("updateWebsiteConfig() was not found")
valid_start = vm.find("            val validPrime =", update_start)
saving_start = vm.find('            _websiteSaveState.value = "saving"', valid_start)
if valid_start >= 0 and saving_start >= 0:
    vm = vm[:valid_start] + vm[saving_start:]
draft_old = '''                if (!draftResponse.isSuccessful) {
                    android.util.Log.e("EloryWebsite", "Publish checkpoint failed: " + draftResponse.code())
                    return@launch
                }
'''
draft_new = '''                if (!draftResponse.isSuccessful) {
                    val detail = runCatching { draftResponse.errorBody()?.string().orEmpty() }.getOrDefault("")
                    android.util.Log.e("EloryWebsite", "Publish checkpoint failed: ${draftResponse.code()} ${detail.take(300)}")
                    _websiteSaveState.value = "error"
                    notifyUser("تعذر حفظ تغييرات الموقع كمسودة (HTTP ${draftResponse.code()}). لم يتم نشر التغييرات.")
                    return@launch
                }
'''
if draft_old in vm:
    vm = vm.replace(draft_old, draft_new, 1)
settings_old = '''                    _websiteSaveState.value = "error"
                    return@launch
                }

                val clearDraftResponse'''
settings_new = '''                    _websiteSaveState.value = "error"
                    notifyUser("لم تكتمل عملية حفظ الموقع. تحقق من الصلاحيات والاتصال ثم أعد المحاولة.")
                    return@launch
                }

                val clearDraftResponse'''
if settings_old in vm:
    vm = vm.replace(settings_old, settings_new, 1)
catch_old = '''                _websiteSaveState.value = "error"
            }
        }
    }

    // Notification management'''
catch_new = '''                _websiteSaveState.value = "error"
                notifyUser(e.message?.take(180) ?: "حدث خطأ أثناء حفظ إعدادات الموقع")
            }
        }
    }

    // Notification management'''
if catch_old in vm:
    vm = vm.replace(catch_old, catch_new, 1)
vm_file.write_text(vm, encoding="utf-8")
print("Website editor tabs, Prime visibility and site save-flow fixes applied.")

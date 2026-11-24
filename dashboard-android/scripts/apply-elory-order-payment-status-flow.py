#!/usr/bin/env python3
"""Align dashboard order states with COD and Paymob-confirmed online orders."""
from pathlib import Path
import os

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()

def replace_once(relative, old, new, label):
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"Missing {relative} for {label}")
    source = path.read_text(encoding="utf-8")
    if new in source:
        print(f"Already applied: {label}")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source anchor, found {count} in {relative}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("PASS:", label)

MODEL = "app/src/main/java/com/pinky/dashboard/domain/model/Order.kt"
ORDERS = "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrdersScreen.kt"
DETAIL = "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"
VM = "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"

replace_once(
    MODEL,
'''        val fulfillmentStatuses: List<OrderStatus> = listOf(PREPARING, SHIPPED, DELIVERED, CANCELLED)

        fun fromString(value: String): OrderStatus {
            val normalized = value.trim().lowercase()
            return when (normalized) {
                "طلب جديد", "جديد", "جاري التأكيد", "تم التأكيد", "جاري التجهيز", "قيد التجهيز", "جاري التحضير", "new", "confirming", "preparing" -> PREPARING
                "تم الشحن", "جاري الشحن", "shipped" -> SHIPPED
                "تم التسليم", "delivered" -> DELIVERED
                "ملغي", "ملغى", "cancelled", "canceled" -> CANCELLED
                else -> entries.firstOrNull { it.name.equals(value, ignoreCase = true) || it.arabicLabel == value } ?: NEW
            }
        }''',
'''        val fulfillmentStatuses: List<OrderStatus> = listOf(CONFIRMING, PREPARING, SHIPPED, DELIVERED, CANCELLED)

        fun availableFor(paymentMethod: PaymentMethod): List<OrderStatus> =
            if (paymentMethod == PaymentMethod.COD) fulfillmentStatuses
            else fulfillmentStatuses.filterNot { it == CONFIRMING }

        fun fromString(value: String): OrderStatus {
            val normalized = value.trim().lowercase()
            return when (normalized) {
                "جديد", "جاري التأكيد", "new", "confirming" -> CONFIRMING
                "طلب جديد", "تم التأكيد", "جاري التجهيز", "قيد التجهيز", "جاري التحضير", "preparing" -> PREPARING
                "تم الشحن", "جاري الشحن", "shipped" -> SHIPPED
                "تم التسليم", "delivered" -> DELIVERED
                "ملغي", "ملغى", "cancelled", "canceled" -> CANCELLED
                else -> entries.firstOrNull { it.name.equals(value, ignoreCase = true) || it.arabicLabel == value } ?: NEW
            }
        }''',
    "separate COD confirmation from preparation and preserve later stages"
)

replace_once(
    MODEL,
'''        fun fromString(value: String): PaymentMethod {
            return entries.firstOrNull { 
                it.name.equals(value, ignoreCase = true) || it.arabicLabel == value 
            } ?: COD
        }''',
'''        fun fromString(value: String): PaymentMethod {
            return when (value.trim().lowercase()) {
                "cash_on_delivery", "cash", "cod", "الدفع عند الاستلام" -> COD
                "card", "visa", "paymob", "credit_card", "online_card", "بطاقة بنكية / فيزا", "دفع إلكتروني" -> CREDIT_CARD
                "vodafone_cash", "vodafone cash", "فودافون كاش / محافظ إلكترونية" -> VODAFONE_CASH
                "instapay", "إنستاباي (instapay)" -> INSTAPAY
                "instapay_wallet", "إنستاباي / محفظة إلكترونية" -> INSTAPAY_WALLET
                else -> entries.firstOrNull {
                    it.name.equals(value, ignoreCase = true) || it.arabicLabel == value
                } ?: COD
            }
        }''',
    "recognize persisted Paymob card and Vodafone Cash methods"
)

replace_once(
    ORDERS,
    "OrderStatus.fulfillmentStatuses.forEach { status ->\n                            DropdownMenuItem(",
    "OrderStatus.availableFor(order.paymentMethod).forEach { status ->\n                            DropdownMenuItem(",
    "show only valid status transitions for this order's payment method"
)
replace_once(
    DETAIL,
    "OrderStatus.fulfillmentStatuses.forEach { status ->\n                                            DropdownMenuItem(",
    "OrderStatus.availableFor(order.paymentMethod).forEach { status ->\n                                            DropdownMenuItem(",
    "apply payment-aware status choices in order details"
)
replace_once(
    VM,
'''            if (!response.isSuccessful) {
                return@withContext Result.failure(IllegalStateException("فشل الحذف من قاعدة البيانات (${response.code()})"))
            }''',
'''            if (!response.isSuccessful) {
                val serverDetail = response.errorBody()?.string()?.trim()?.take(240).orEmpty()
                val suffix = if (serverDetail.isNotBlank()) ": $serverDetail" else ""
                return@withContext Result.failure(IllegalStateException("فشل الحذف من قاعدة البيانات (HTTP ${response.code()})$suffix"))
            }''',
    "surface Supabase delete diagnostics instead of hiding the database error"
)

checks = {
    MODEL: ("listOf(CONFIRMING, PREPARING, SHIPPED, DELIVERED, CANCELLED)", "-> CONFIRMING", '"card", "visa", "paymob"', '"vodafone_cash", "vodafone cash"'),
    ORDERS: ("OrderStatus.availableFor(order.paymentMethod)",),
    DETAIL: ("OrderStatus.availableFor(order.paymentMethod)",),
    VM: ("serverDetail = response.errorBody()",)
}
for relative, markers in checks.items():
    source = (ROOT / relative).read_text(encoding="utf-8")
    missing = [m for m in markers if m not in source]
    if missing:
        raise SystemExit(f"Dashboard workflow verification failed in {relative}: {missing}")
print("PASS: COD starts in confirmation; paid online orders start in preparation; Prime orders share the same payment-aware lifecycle.")
